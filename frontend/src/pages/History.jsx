import { useState, useMemo } from 'react';
import { Menu, Clock, Download, Search, RotateCcw } from 'lucide-react';
import Sidebar from '../components/layout/Sidebar';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import SimulationBadge from '../components/ui/SimulationBadge';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import ThemeToggle from '../components/ui/ThemeToggle';
import { useDetections } from '../hooks/useDetections';
import { useEvents } from '../hooks/useEvents';
import { formatTimestamp, formatConfidence } from '../utils/format';
import { JUNCTIONS } from '../utils/constants';

const ITEMS_PER_PAGE = 20;

export default function History() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('all'); // 'detections' | 'signals' | 'all'
  const [filterJunction, setFilterJunction] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [filterDateFrom, setFilterDateFrom] = useState('');
  const [filterDateTo, setFilterDateTo] = useState('');
  const [currentPage, setCurrentPage] = useState(1);

  const { detections, loading: detectLoading } = useDetections(100);
  const { events, loading: eventsLoading } = useEvents(100);

  // Normalize data for Unified View
  const normalizedRecords = useMemo(() => {
    const list = [];

    if (activeTab === 'detections' || activeTab === 'all') {
      detections.forEach((d) => {
        list.push({
          id: d.id || `det-${d.created_at}`,
          category: 'DETECTION',
          type: d.is_siren ? 'SIREN DETECTED' : 'NO SIREN',
          is_siren: d.is_siren,
          confidence: d.confidence,
          junction_id: d.junction_id || '—',
          approach: d.approach || '—',
          details: `Model: ${d.model_type || '—'}, Conf: ${formatConfidence(d.confidence)}`,
          created_at: d.created_at || d.timestamp || '',
          raw: d,
        });
      });
    }

    if (activeTab === 'signals' || activeTab === 'all') {
      events.forEach((e) => {
        list.push({
          id: e.id || `sig-${e.created_at}`,
          category: 'SIGNAL_EVENT',
          type: `${e.from_state || 'NORMAL'} → ${e.to_state || e.state || 'NORMAL'}`,
          junction_id: e.junction_id || e.junction || '—',
          approach: e.approach || '—',
          details: `Trigger: ${e.trigger || '—'}, Amb: ${e.ambulance_id || '—'}`,
          created_at: e.created_at || e.timestamp || '',
          raw: e,
        });
      });
    }

    // Sort by timestamp descending
    list.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

    // Filter by junction
    let filtered = list;
    if (filterJunction !== 'ALL') {
      filtered = filtered.filter((item) => item.junction_id === filterJunction);
    }

    // Filter by search query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (item) =>
          item.type.toLowerCase().includes(q) ||
          item.junction_id.toLowerCase().includes(q) ||
          item.details.toLowerCase().includes(q) ||
          item.approach.toLowerCase().includes(q)
      );
    }

    // Filter by date range
    if (filterDateFrom) {
      const fromTime = new Date(filterDateFrom).getTime();
      filtered = filtered.filter((item) => new Date(item.created_at).getTime() >= fromTime);
    }
    if (filterDateTo) {
      const toTime = new Date(filterDateTo).getTime() + 86400000; // End of day
      filtered = filtered.filter((item) => new Date(item.created_at).getTime() <= toTime);
    }

    return filtered;
  }, [activeTab, detections, events, filterJunction, searchQuery, filterDateFrom, filterDateTo]);

  const totalPages = Math.max(1, Math.ceil(normalizedRecords.length / ITEMS_PER_PAGE));
  const pagedRecords = normalizedRecords.slice(
    (currentPage - 1) * ITEMS_PER_PAGE,
    currentPage * ITEMS_PER_PAGE
  );

  const handleExport = () => {
    const jsonStr = JSON.stringify(normalizedRecords, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `lifelane-history-${activeTab}-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const resetFilters = () => {
    setFilterJunction('ALL');
    setSearchQuery('');
    setFilterDateFrom('');
    setFilterDateTo('');
    setCurrentPage(1);
  };

  const isLoading = detectLoading || eventsLoading;

  return (
    <div className="ops-page min-h-screen bg-[#F6F8F7] flex">
      <Sidebar mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} />

      <div className="flex-1 lg:pl-64 flex flex-col">
        {/* Top Header */}
        <header className="ops-header sticky top-0 z-20 bg-white border-b border-gray-200 px-4 sm:px-6 py-3 flex items-center gap-3">
          <button
            className="lg:hidden p-2 rounded-md hover:bg-gray-100"
            onClick={() => setMobileOpen(true)}
            aria-label="Open menu"
          >
            <Menu className="w-5 h-5 text-gray-600" />
          </button>
          <Clock className="w-5 h-5 text-[#087F5B]" />
          <div className="flex-1 min-w-0">
            <h1 className="font-bold text-gray-900 text-lg truncate">Audit & Event History</h1>
          </div>
          <SimulationBadge />
          <ThemeToggle />
          <Button size="sm" variant="secondary" onClick={handleExport} className="flex items-center gap-1.5">
            <Download className="w-4 h-4" />
            <span className="hidden sm:inline">Export JSON</span>
          </Button>
        </header>

        <main className="flex-1 p-4 sm:p-6 space-y-6">
          {/* Tabs */}
          <div className="flex border-b border-gray-200">
            {[
              { id: 'all', label: 'All Events' },
              { id: 'detections', label: 'Detections' },
              { id: 'signals', label: 'Signal Events' },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => {
                  setActiveTab(tab.id);
                  setCurrentPage(1);
                }}
                className={`py-3 px-6 text-sm font-semibold border-b-2 transition-colors cursor-pointer ${
                  activeTab === tab.id
                    ? 'border-[#087F5B] text-[#087F5B]'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Filters Bar */}
          <Card padding={false} className="p-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 items-end">
              {/* Search */}
              <div className="lg:col-span-2">
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                  Search
                </label>
                <div className="relative">
                  <Search className="w-4 h-4 absolute left-3 top-2.5 text-gray-400" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => {
                      setSearchQuery(e.target.value);
                      setCurrentPage(1);
                    }}
                    placeholder="Search trigger, ambulance, approach..."
                    className="w-full pl-9 pr-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#087F5B]"
                  />
                </div>
              </div>

              {/* Junction select */}
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                  Junction
                </label>
                <select
                  value={filterJunction}
                  onChange={(e) => {
                    setFilterJunction(e.target.value);
                    setCurrentPage(1);
                  }}
                  className="w-full py-1.5 px-3 text-sm border border-gray-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-[#087F5B]"
                >
                  <option value="ALL">All Junctions</option>
                  {JUNCTIONS.map((j) => (
                    <option key={j.id} value={j.id}>{j.name}</option>
                  ))}
                </select>
              </div>

              {/* Date From */}
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                  From Date
                </label>
                <input
                  type="date"
                  value={filterDateFrom}
                  onChange={(e) => {
                    setFilterDateFrom(e.target.value);
                    setCurrentPage(1);
                  }}
                  className="w-full py-1.5 px-2 text-sm border border-gray-300 rounded-lg bg-white"
                />
              </div>

              {/* Reset action */}
              <div className="flex gap-2">
                <div className="flex-1">
                  <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                    To Date
                  </label>
                  <input
                    type="date"
                    value={filterDateTo}
                    onChange={(e) => {
                      setFilterDateTo(e.target.value);
                      setCurrentPage(1);
                    }}
                    className="w-full py-1.5 px-2 text-sm border border-gray-300 rounded-lg bg-white"
                  />
                </div>
                <button
                  onClick={resetFilters}
                  title="Reset Filters"
                  className="p-2 border border-gray-300 rounded-lg text-gray-500 hover:bg-gray-100 transition-colors self-end mb-0.5 cursor-pointer"
                >
                  <RotateCcw className="w-4 h-4" />
                </button>
              </div>
            </div>
          </Card>

          {/* Results Summary & Pagination Header */}
          <div className="flex items-center justify-between text-xs text-gray-500 px-1">
            <span>
              Showing {normalizedRecords.length === 0 ? 0 : (currentPage - 1) * ITEMS_PER_PAGE + 1}–
              {Math.min(currentPage * ITEMS_PER_PAGE, normalizedRecords.length)} of {normalizedRecords.length} records
            </span>
            <span>Simulation Log Data</span>
          </div>

          {/* Data List */}
          <Card padding={false} className="overflow-hidden">
            {isLoading ? (
              <div className="py-12">
                <LoadingSpinner />
              </div>
            ) : normalizedRecords.length === 0 ? (
              <div className="text-center py-12 text-sm text-gray-400">
                No matching records found
              </div>
            ) : (
              <>
                {/* Desktop Table View */}
                <div className="hidden md:block overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-gray-50 border-b border-gray-200 text-gray-500 uppercase tracking-wider font-semibold">
                      <tr>
                        <th className="py-3 px-4">Timestamp</th>
                        <th className="py-3 px-4">Category</th>
                        <th className="py-3 px-4">Junction</th>
                        <th className="py-3 px-4">Approach</th>
                        <th className="py-3 px-4">Event / Result</th>
                        <th className="py-3 px-4">Technical Details</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {pagedRecords.map((item, idx) => {
                        const isDet = item.category === 'DETECTION';
                        return (
                          <tr key={item.id || idx} className="hover:bg-gray-50 transition-colors">
                            <td className="py-3 px-4 text-gray-500 whitespace-nowrap">
                              {formatTimestamp(item.created_at)}
                            </td>
                            <td className="py-3 px-4">
                              <span
                                className={`inline-flex px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                                  isDet ? 'bg-purple-100 text-purple-800' : 'bg-emerald-100 text-emerald-800'
                                }`}
                              >
                                {isDet ? 'AUDIO' : 'SIGNAL'}
                              </span>
                            </td>
                            <td className="py-3 px-4 font-bold text-gray-800">
                              {item.junction_id}
                            </td>
                            <td className="py-3 px-4 capitalize text-gray-600">
                              {item.approach}
                            </td>
                            <td className="py-3 px-4">
                              {isDet ? (
                                <span className={`font-semibold ${item.is_siren ? 'text-red-600' : 'text-green-700'}`}>
                                  {item.type}
                                </span>
                              ) : (
                                <span className="font-semibold text-gray-900">{item.type}</span>
                              )}
                            </td>
                            <td className="py-3 px-4 text-gray-500 font-mono text-[11px]">
                              {item.details}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Mobile Card View */}
                <div className="md:hidden divide-y divide-gray-100">
                  {pagedRecords.map((item, idx) => {
                    const isDet = item.category === 'DETECTION';
                    return (
                      <div key={item.id || idx} className="p-4 space-y-1.5">
                        <div className="flex items-center justify-between">
                          <span
                            className={`inline-flex px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                              isDet ? 'bg-purple-100 text-purple-800' : 'bg-emerald-100 text-emerald-800'
                            }`}
                          >
                            {isDet ? 'AUDIO DETECTION' : 'SIGNAL TRANSITION'}
                          </span>
                          <span className="text-[11px] text-gray-400">
                            {formatTimestamp(item.created_at)}
                          </span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-sm text-gray-800">
                            {item.junction_id} • Approach: <span className="capitalize">{item.approach}</span>
                          </span>
                          <span className="font-semibold text-xs text-gray-900">
                            {item.type}
                          </span>
                        </div>
                        <p className="text-xs text-gray-500 font-mono bg-gray-50 p-2 rounded">
                          {item.details}
                        </p>
                      </div>
                    );
                  })}
                </div>

                {/* Pagination Controls */}
                {totalPages > 1 && (
                  <div className="flex items-center justify-between p-4 border-t border-gray-200 text-xs">
                    <span className="text-gray-500">
                      Page {currentPage} of {totalPages}
                    </span>
                    <div className="flex gap-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={currentPage === 1}
                        onClick={() => setCurrentPage((p) => p - 1)}
                      >
                        Previous
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={currentPage === totalPages}
                        onClick={() => setCurrentPage((p) => p + 1)}
                      >
                        Next
                      </Button>
                    </div>
                  </div>
                )}
              </>
            )}
          </Card>
        </main>
      </div>
    </div>
  );
}
