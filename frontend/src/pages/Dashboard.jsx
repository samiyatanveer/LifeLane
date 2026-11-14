import { useState, useEffect } from 'react';
import { Menu, RefreshCw } from 'lucide-react';
import Sidebar from '../components/layout/Sidebar';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import StatusDot from '../components/ui/StatusDot';
import SimulationBadge from '../components/ui/SimulationBadge';
import Alert from '../components/ui/Alert';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import DetectionChart from '../components/charts/DetectionChart';
import { useHealth } from '../hooks/useHealth';
import { useDetections } from '../hooks/useDetections';
import { useSignals } from '../hooks/useSignals';
import { useEvents } from '../hooks/useEvents';
import { formatRelativeTime, formatUptime, formatCurrentTime } from '../utils/format';
import { getModelInfo } from '../api/health';

const STATE_COLOR_MAP = {
  NORMAL: 'bg-green-100 border-green-300 text-green-900',
  SUSPECTED: 'bg-amber-100 border-amber-300 text-amber-900',
  CONFIRMED: 'bg-amber-100 border-amber-300 text-amber-900',
  PREPARING: 'bg-orange-100 border-orange-300 text-orange-900',
  SERVING: 'bg-red-100 border-red-300 text-red-900',
  RECOVERING: 'bg-blue-100 border-blue-300 text-blue-900',
};

const STATE_DOT_COLOR = {
  NORMAL: 'green',
  SUSPECTED: 'amber',
  CONFIRMED: 'amber',
  PREPARING: 'amber',
  SERVING: 'red',
  RECOVERING: 'blue',
};

function JunctionCard({ junction }) {
  const state = junction?.state || 'NORMAL';
  const colorCls = STATE_COLOR_MAP[state] || STATE_COLOR_MAP.NORMAL;
  const dotColor = STATE_DOT_COLOR[state] || 'gray';
  const isServing = state === 'SERVING';

  return (
    <div
      className={`rounded-xl border-2 p-4 ${colorCls} ${isServing ? 'ring-2 ring-red-400 ring-offset-1' : ''} transition-all`}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="font-bold text-base">{junction?.junction_id || junction?.id || '—'}</span>
        <div className="flex items-center gap-1.5">
          <StatusDot color={dotColor} animate={isServing} />
          <Badge state={state}>{state}</Badge>
        </div>
      </div>
      {junction?.approach && (
        <p className="text-xs opacity-75 mt-1">Approach: <span className="font-medium capitalize">{junction.approach}</span></p>
      )}
      {junction?.ambulance_id && (
        <p className="text-xs opacity-75">Ambulance: <span className="font-medium">{junction.ambulance_id}</span></p>
      )}
    </div>
  );
}

function StatCard({ label, value, sub, loading }) {
  return (
    <Card>
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">{label}</p>
      {loading ? (
        <div className="h-8 w-16 bg-gray-100 rounded animate-pulse" />
      ) : (
        <p className="text-3xl font-extrabold text-gray-900">{value ?? '—'}</p>
      )}
      {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
    </Card>
  );
}

export default function Dashboard() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [currentTime, setCurrentTime] = useState(formatCurrentTime());
  const [modelInfo, setModelInfo] = useState(null);

  const { health, stats, online, error: healthError, lastUpdated, refetch } = useHealth(10000);
  const { detections, loading: detectLoading } = useDetections(20, 10000);
  const { signals } = useSignals(5000);
  const { events, loading: eventsLoading } = useEvents(10, 5000);

  useEffect(() => {
    const id = setInterval(() => setCurrentTime(formatCurrentTime()), 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    getModelInfo().then(setModelInfo).catch(() => {});
  }, []);

  // Build 4 junctions from signals, filling gaps with defaults
  const JUNCTION_IDS = ['J1', 'J2', 'J3', 'J4'];
  const signalMap = {};
  signals.forEach((s) => { signalMap[s.junction_id || s.id] = s; });
  const junctions = JUNCTION_IDS.map((id) => signalMap[id] || { junction_id: id, id, state: 'NORMAL' });

  return (
    <div className="min-h-screen bg-[#F6F8F7] flex">
      <Sidebar mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} />

      <div className="flex-1 lg:pl-64 flex flex-col">
        {/* Top bar */}
        <header className="sticky top-0 z-20 bg-white border-b border-gray-200 px-4 sm:px-6 py-3 flex items-center gap-3">
          <button
            className="lg:hidden p-2 rounded-md hover:bg-gray-100"
            onClick={() => setMobileOpen(true)}
            aria-label="Open menu"
          >
            <Menu className="w-5 h-5 text-gray-600" />
          </button>
          <div className="flex-1 min-w-0">
            <h1 className="font-bold text-gray-900 text-base sm:text-lg truncate">Operations Dashboard</h1>
            <p className="text-xs text-gray-400 hidden sm:block">{currentTime}</p>
          </div>
          <SimulationBadge />
          <button
            onClick={refetch}
            className="p-2 rounded-md hover:bg-gray-100 text-gray-500"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </header>

        <main className="flex-1 p-4 sm:p-6 space-y-6">
          {/* Backend status */}
          {online === false && (
            <Alert variant="error" title="Backend Offline">
              Cannot connect to backend at http://localhost:8000. {healthError}
              <button onClick={refetch} className="ml-2 underline text-xs">Retry</button>
            </Alert>
          )}
          {online === true && (
            <div className="flex items-center gap-2 text-sm text-green-700 bg-green-50 border border-green-200 rounded-lg px-4 py-2">
              <StatusDot color="green" />
              <span className="font-medium">Backend Online</span>
              {lastUpdated && <span className="text-green-500 text-xs ml-auto">Updated {formatRelativeTime(lastUpdated)}</span>}
            </div>
          )}

          {/* Stats row */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              label="System Status"
              value={health ? (health.status === 'ok' ? '✓ OK' : health.status) : (online === false ? 'Offline' : '—')}
              sub={health?.uptime_s ? `Up ${formatUptime(health.uptime_s)}` : undefined}
              loading={online === null}
            />
            <StatCard
              label="Total Detections"
              value={stats?.total_detections ?? (online === false ? '—' : '...')}
              sub="All time"
              loading={online === null}
            />
            <StatCard
              label="Active Requests"
              value={stats?.active_requests ?? '—'}
              sub="In progress"
              loading={online === null}
            />
            <StatCard
              label="Junctions Serving"
              value={stats?.junctions_serving ?? '—'}
              sub="Of 4 total"
              loading={online === null}
            />
          </div>

          {/* Model status */}
          {modelInfo && (
            <Card>
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-sm font-semibold text-gray-700">ML Model:</span>
                <Badge state={modelInfo.model_type?.split('_')[0]}>{modelInfo.model_type}</Badge>
                {modelInfo.threshold != null && (
                  <span className="text-xs text-gray-500">Threshold: {modelInfo.threshold}</span>
                )}
                {modelInfo.is_synthetic && (
                  <Alert variant="warning" className="mt-0 py-1 px-3 text-xs flex-1">
                    Running on synthetic/mock model — accuracy is limited.
                  </Alert>
                )}
              </div>
            </Card>
          )}

          {/* Junction grid */}
          <div>
            <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-3">Junction Status</h2>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {junctions.map((j) => (
                <JunctionCard key={j.junction_id || j.id} junction={j} />
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            {/* Detection chart */}
            <Card>
              <h2 className="text-sm font-semibold text-gray-700 mb-4">Detection Overview (Last 20)</h2>
              {detectLoading ? <LoadingSpinner /> : <DetectionChart detections={detections} />}
            </Card>

            {/* Recent events */}
            <Card>
              <h2 className="text-sm font-semibold text-gray-700 mb-4">Recent Events</h2>
              {eventsLoading ? (
                <LoadingSpinner />
              ) : events.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-6">No events yet</p>
              ) : (
                <ul className="space-y-2 max-h-64 overflow-y-auto">
                  {events.slice(0, 10).map((e, i) => (
                    <li key={i} className="flex gap-3 text-xs py-2 border-b border-gray-100 last:border-0">
                      <span className="text-gray-400 flex-shrink-0 w-16">{formatRelativeTime(e.created_at || e.timestamp)}</span>
                      <span className="text-gray-700 flex-1">{e.trigger || e.event_type || e.type || 'Event'}</span>
                      {(e.junction_id || e.junction) && (
                        <span className="text-gray-400 flex-shrink-0">{e.junction_id || e.junction}</span>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        </main>
      </div>
    </div>
  );
}
