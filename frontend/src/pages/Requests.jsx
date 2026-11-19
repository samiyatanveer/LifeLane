import { useState } from 'react';
import { Menu, FileText, PlusCircle, RefreshCw, ChevronDown } from 'lucide-react';
import Sidebar from '../components/layout/Sidebar';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';
import Alert from '../components/ui/Alert';
import EmptyState from '../components/ui/EmptyState';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import SimulationBadge from '../components/ui/SimulationBadge';
import { createRequest, updateRequestStatus, getRouteOptions, startTemporaryVerification, confirmTemporaryVerification, authorizePriority } from '../api/dispatch';
import { useAuth } from '../auth/AuthContext';
import { useRequests } from '../hooks/useRequests';
import { useAmbulances } from '../hooks/useAmbulances';
import { formatTimestamp } from '../utils/format';
import { APPROACHES, JUNCTIONS } from '../utils/constants';

const EMERGENCY_MODES = ['EMERGENCY', 'URGENT', 'ROUTINE'];
const VALID_STATUSES = ['PENDING', 'ACTIVE', 'COMPLETED', 'CANCELLED'];

const INITIAL_FORM = {
  ambulance_id: '',
  origin_edge: '',
  destination_edge: '',
  hospital_id: '',
  approach: 'north',
  junction_id: 'J1',
  emergency_mode: 'EMERGENCY',
};

function StatusPill({ status }) {
  const map = {
    PENDING: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    ACTIVE: 'bg-green-100 text-green-800 border-green-200',
    COMPLETED: 'bg-gray-100 text-gray-700 border-gray-200',
    CANCELLED: 'bg-red-50 text-red-700 border-red-200',
  };
  const cls = map[status] || 'bg-gray-100 text-gray-700 border-gray-200';
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${cls}`}>
      {status}
    </span>
  );
}

function StatusDropdown({ requestId, currentStatus, onUpdate }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSelect = async (status) => {
    if (status === currentStatus) { setOpen(false); return; }
    setLoading(true);
    setOpen(false);
    try {
      await onUpdate(requestId, status);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative inline-block">
      <button
        onClick={() => setOpen((v) => !v)}
        disabled={loading}
        className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 border border-gray-300 rounded px-2 py-1 bg-white hover:bg-gray-50 transition-colors cursor-pointer"
      >
        {loading ? '…' : 'Update'}
        <ChevronDown className="w-3 h-3" />
      </button>
      {open && (
        <div className="absolute right-0 mt-1 w-36 bg-white border border-gray-200 rounded-lg shadow-lg z-10 overflow-hidden">
          {VALID_STATUSES.map((s) => (
            <button
              key={s}
              onClick={() => handleSelect(s)}
              className={`block w-full text-left px-3 py-2 text-xs font-medium hover:bg-gray-50 transition-colors cursor-pointer ${s === currentStatus ? 'text-[#087F5B] bg-green-50' : 'text-gray-700'}`}
            >
              {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Requests() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(INITIAL_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [submitSuccess, setSubmitSuccess] = useState(null);
  const [updateError, setUpdateError] = useState(null);
  const [routes, setRoutes] = useState([]); const [temp, setTemp] = useState(null); const [tempCode, setTempCode] = useState('');
  const { user } = useAuth();

  const { requests, loading, error, refetch } = useRequests(10000);
  const { ambulances } = useAmbulances();

  const handleChange = (e) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
    setSubmitError(null);
  };

  const validate = () => {
    if (user?.role !== 'AMBULANCE' && !form.ambulance_id.trim()) return 'Select a registered ambulance or complete temporary verification.';
    if (!form.origin_edge.trim()) return 'Origin edge is required.';
    if (!form.destination_edge.trim()) return 'Destination edge is required.';
    if (!form.hospital_id.trim()) return 'Hospital ID is required.';
    return null;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const err = validate();
    if (err) { setSubmitError(err); return; }
    setSubmitting(true);
    setSubmitError(null);
    setSubmitSuccess(null);
    try {
      const result = await createRequest({
        ...(user?.role === 'AMBULANCE' ? {} : { ambulance_id: form.ambulance_id.trim() }),
        origin_edge: form.origin_edge.trim(),
        destination_edge: form.destination_edge.trim(),
        hospital_id: form.hospital_id.trim(),
        approach: form.approach,
        junction_id: form.junction_id,
        emergency_mode: form.emergency_mode,
        selected_route_id: form.selected_route_id || 'fastest',
      });
      setSubmitSuccess(`Emergency request created! Request ID: ${result.request_id}`);
      setForm(INITIAL_FORM);
      setShowForm(false);
      refetch();
    } catch (err) {
      setSubmitError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const previewRoutes = async () => { if (!form.origin_edge || !form.destination_edge) return setSubmitError('Enter origin and destination before previewing routes.'); try { const choices = await getRouteOptions(form.origin_edge, form.destination_edge); setRoutes(choices); setForm(p => ({...p, selected_route_id: choices.find(r => r.recommended)?.id || choices[0]?.id})); } catch (err) { setSubmitError(err.message); } };
  const beginTemporary = async () => { try { const result = await startTemporaryVerification({ contact_phone: form.temp_phone || '', vehicle_registration: form.temp_registration || '', verification_method: 'SMS' }); setTemp(result); } catch (err) { setSubmitError(err.message); } };
  const verifyTemporary = async () => { try { const result = await confirmTemporaryVerification({ temporary_id: temp.temporary_id, code: tempCode }); setTemp(result); setForm(p => ({...p, ambulance_id: result.temporary_id})); } catch (err) { setSubmitError(err.message); } };
  const activate = async (id) => { try { await authorizePriority(id); refetch(); } catch (err) { setUpdateError(err.message); } };

  const handleUpdateStatus = async (requestId, status) => {
    setUpdateError(null);
    try {
      await updateRequestStatus(requestId, status);
      refetch();
    } catch (err) {
      setUpdateError(`Failed to update request ${requestId}: ${err.message}`);
    }
  };

  const pendingCount = requests.filter((r) => r.status === 'PENDING').length;
  const activeCount = requests.filter((r) => r.status === 'ACTIVE').length;

  return (
    <div className="ops-page min-h-screen bg-[#F6F8F7] flex">
      <Sidebar mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} />

      <div className="flex-1 lg:pl-64 flex flex-col">
        <header className="ops-header sticky top-0 z-20 bg-white border-b border-gray-200 px-4 sm:px-6 py-3 flex items-center gap-3">
          <button className="lg:hidden p-2 rounded-md hover:bg-gray-100" onClick={() => setMobileOpen(true)} aria-label="Open menu">
            <Menu className="w-5 h-5 text-gray-600" />
          </button>
          <FileText className="w-5 h-5 text-[#087F5B]" />
          <div className="flex-1 min-w-0">
            <h1 className="font-bold text-gray-900 text-lg truncate">Emergency Requests</h1>
          </div>
          <SimulationBadge />
          <button onClick={refetch} className="p-2 rounded-md hover:bg-gray-100 text-gray-500" title="Refresh">
            <RefreshCw className="w-4 h-4" />
          </button>
          <Button size="sm" onClick={() => { setShowForm((v) => !v); setSubmitError(null); }} className="flex items-center gap-1.5">
            <PlusCircle className="w-4 h-4" />
            <span className="hidden sm:inline">New Request</span>
          </Button>
        </header>

        <main className="flex-1 p-4 sm:p-6 space-y-6">

          {/* Success banner */}
          {submitSuccess && (
            <Alert variant="success" title="Request Created" dismissible onClose={() => setSubmitSuccess(null)}>
              {submitSuccess}
            </Alert>
          )}

          {updateError && (
            <Alert variant="error" dismissible onClose={() => setUpdateError(null)}>{updateError}</Alert>
          )}

          {/* Stats */}
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: 'Total', value: requests.length, color: 'text-gray-900' },
              { label: 'Pending', value: pendingCount, color: 'text-yellow-700' },
              { label: 'Active', value: activeCount, color: 'text-green-700' },
            ].map((s) => (
              <Card key={s.label} className="text-center">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{s.label}</p>
                <p className={`text-3xl font-extrabold mt-1 ${s.color}`}>{s.value}</p>
              </Card>
            ))}
          </div>

          {/* New Request Form */}
          {showForm && (
            <Card>
              <h2 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <PlusCircle className="w-5 h-5 text-[#087F5B]" />
                Create Emergency Request
              </h2>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {user?.role !== 'AMBULANCE' && <div>
                    <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1.5">
                      Ambulance (LifeLane ID) <span className="text-red-500">*</span>
                    </label>
                    {ambulances.length > 0 ? (
                      <select
                        name="ambulance_id"
                        value={form.ambulance_id}
                        onChange={handleChange}
                        className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#087F5B]"
                      >
                        <option value="">— Select ambulance —</option>
                        {ambulances.map((a) => (
                          <option key={a.id} value={a.lifelane_id}>
                            {a.lifelane_id} · {a.registration_number} ({a.service_name})
                          </option>
                        ))}
                      </select>
                    ) : <p className="text-sm text-amber-700">No registered ambulances available. Use temporary verification below.</p>}
                  </div>}
                  {user?.role === 'AMBULANCE' && <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900"><b>Registered ambulance:</b> {user?.ambulance?.lifelane_id || 'Loading your linked ambulance…'}. Your identity is applied automatically.</div>}
                  <div>
                    <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1.5">
                      Emergency Mode
                    </label>
                    <select
                      name="emergency_mode"
                      value={form.emergency_mode}
                      onChange={handleChange}
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#087F5B]"
                    >
                      {EMERGENCY_MODES.map((m) => <option key={m} value={m}>{m}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1.5">
                      Origin Edge <span className="text-red-500">*</span>
                      <span className="ml-1 text-gray-400 normal-case font-normal">(SUMO road edge)</span>
                    </label>
                    <input
                      type="text"
                      name="origin_edge"
                      value={form.origin_edge}
                      onChange={handleChange}
                      placeholder="e.g. edge_0_1_0"
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#087F5B]"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1.5">
                      Destination Edge <span className="text-red-500">*</span>
                      <span className="ml-1 text-gray-400 normal-case font-normal">(SUMO road edge)</span>
                    </label>
                    <input
                      type="text"
                      name="destination_edge"
                      value={form.destination_edge}
                      onChange={handleChange}
                      placeholder="e.g. edge_3_2_0"
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#087F5B]"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1.5">
                      Hospital ID <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      name="hospital_id"
                      value={form.hospital_id}
                      onChange={handleChange}
                      placeholder="e.g. HOSP-01"
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#087F5B]"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1.5">
                      Approach Direction
                    </label>
                    <select
                      name="approach"
                      value={form.approach}
                      onChange={handleChange}
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#087F5B]"
                    >
                      {APPROACHES.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1.5">
                      Junction
                    </label>
                    <select
                      name="junction_id"
                      value={form.junction_id}
                      onChange={handleChange}
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#087F5B]"
                    >
                      {JUNCTIONS.map((j) => <option key={j.id} value={j.id}>{j.name}</option>)}
                    </select>
                  </div>
                </div>

                <div className="rounded-xl border border-emerald-100 bg-emerald-50/50 p-4 space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2"><div><p className="font-semibold text-gray-900">Route selection</p><p className="text-xs text-gray-500">Review simulated corridor junctions before submitting.</p></div><Button type="button" variant="secondary" size="sm" onClick={previewRoutes}>Preview routes</Button></div>
                  {routes.length > 0 && <div className="grid gap-2 md:grid-cols-3">{routes.map(route => <label key={route.id} className={`cursor-pointer rounded-lg border p-3 text-sm ${form.selected_route_id === route.id ? 'border-[#087F5B] bg-white' : 'border-gray-200 bg-white/60'}`}><input className="mr-2" type="radio" name="selected_route_id" value={route.id} checked={form.selected_route_id === route.id} onChange={handleChange}/><b>{route.label}</b>{route.recommended && <span className="ml-1 text-xs text-[#087F5B]">FASTEST</span>}<span className="mt-1 block text-xs text-gray-500">{route.eta_minutes} min · {route.distance_km} km · {route.junctions.join(' → ')}</span></label>)}</div>}
                </div>

                {user?.role !== 'AMBULANCE' && <div className="rounded-xl border border-amber-200 bg-amber-50 p-4"><p className="font-semibold text-amber-900">Temporary ambulance verification</p><p className="text-xs text-amber-800">Required before a non-registered ambulance can submit. The code is displayed only for this academic simulation.</p>{!temp && <div className="mt-3 flex flex-wrap gap-2"><input value={form.temp_phone || ''} onChange={e=>setForm(p=>({...p,temp_phone:e.target.value}))} placeholder="Contact phone" className="rounded-lg border px-3 py-2 text-sm"/><input value={form.temp_registration || ''} onChange={e=>setForm(p=>({...p,temp_registration:e.target.value}))} placeholder="Vehicle registration" className="rounded-lg border px-3 py-2 text-sm"/><Button type="button" size="sm" onClick={beginTemporary}>Send simulation code</Button></div>}{temp?.status === 'PENDING' && <div className="mt-3 flex flex-wrap items-center gap-2"><span className="text-sm">Simulation code: <b>{temp.verification_hint}</b></span><input value={tempCode} onChange={e=>setTempCode(e.target.value)} placeholder="6-digit code" className="rounded-lg border px-3 py-2 text-sm"/><Button type="button" size="sm" onClick={verifyTemporary}>Verify</Button></div>}{temp?.status === 'VERIFIED' && <p className="mt-2 text-sm font-semibold text-green-700">Temporary ID {temp.temporary_id} verified; it expires at {formatTimestamp(temp.expires_at)}.</p>}</div>}

                {submitError && <Alert variant="error">{submitError}</Alert>}

                <div className="flex gap-3 pt-2">
                  <Button type="submit" loading={submitting} disabled={submitting}>
                    {submitting ? 'Creating…' : 'Create Emergency Request'}
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => { setShowForm(false); setSubmitError(null); setForm(INITIAL_FORM); }}
                  >
                    Cancel
                  </Button>
                </div>
              </form>
            </Card>
          )}

          {/* Error from listing */}
          {error && (
            <Alert variant="error" title="Failed to load requests">
              {error}
              <button onClick={refetch} className="ml-2 underline text-xs">Retry</button>
            </Alert>
          )}

          {/* Requests list */}
          <Card padding={false}>
            <div className="flex items-center justify-between p-5 border-b border-gray-200">
              <div>
                <p className="section-eyebrow">Dispatch</p>
                <h2 className="mt-1 text-lg font-bold text-gray-900">All Emergency Requests</h2>
              </div>
              <span className="text-sm text-gray-500 font-semibold">{requests.length} total</span>
            </div>

            {loading ? (
              <div className="py-12"><LoadingSpinner /></div>
            ) : requests.length === 0 ? (
              <div className="py-8">
                <EmptyState
                  icon={FileText}
                  title="No emergency requests"
                  message='Use "New Request" to dispatch the first emergency request.'
                />
              </div>
            ) : (
              <>
                {/* Desktop table */}
                <div className="hidden md:block overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left border-b border-gray-200 bg-gray-50">
                        {['Request ID', 'Ambulance', 'Hospital', 'Junction', 'Mode', 'Status', 'Created', 'Actions'].map((h) => (
                          <th key={h} className="py-3 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {requests.map((req) => (
                        <tr key={req.id} className="hover:bg-gray-50 transition-colors">
                          <td className="py-3 px-4 font-mono text-xs font-bold text-[#087F5B]">{req.request_id}</td>
                          <td className="py-3 px-4 font-mono text-xs text-gray-700">{req.ambulance_id}</td>
                          <td className="py-3 px-4 text-xs text-gray-600">{req.hospital_id}</td>
                          <td className="py-3 px-4 font-bold text-gray-800">{req.junction_id}</td>
                          <td className="py-3 px-4">
                            <Badge>{req.emergency_mode}</Badge>
                          </td>
                          <td className="py-3 px-4">
                            <StatusPill status={req.status} />
                          </td>
                          <td className="py-3 px-4 text-xs text-gray-400">{formatTimestamp(req.created_at)}</td>
                          <td className="py-3 px-4">
                            {['DISPATCHER','ADMIN'].includes(user?.role) && req.status === 'PENDING' ? <Button size="sm" onClick={() => activate(req.request_id)}>Authorize priority</Button> : <StatusDropdown
                              requestId={req.request_id}
                              currentStatus={req.status}
                              onUpdate={handleUpdateStatus}
                            />}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Mobile cards */}
                <div className="md:hidden divide-y divide-gray-100">
                  {requests.map((req) => (
                    <div key={req.id} className="p-4 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-xs font-bold text-[#087F5B]">{req.request_id}</span>
                        <StatusPill status={req.status} />
                      </div>
                      <div className="text-xs text-gray-600">Ambulance: <span className="font-mono font-semibold">{req.ambulance_id}</span></div>
                      <div className="text-xs text-gray-600">Hospital: {req.hospital_id} · Junction: {req.junction_id}</div>
                      <div className="flex items-center justify-between pt-1">
                        <span className="text-xs text-gray-400">{formatTimestamp(req.created_at)}</span>
                        <StatusDropdown
                          requestId={req.request_id}
                          currentStatus={req.status}
                          onUpdate={handleUpdateStatus}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </Card>
        </main>
      </div>
    </div>
  );
}
