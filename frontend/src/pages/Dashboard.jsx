import { useState, useEffect } from 'react';
import { Menu, RefreshCw, Activity, MapPinned, Radio } from 'lucide-react';
import Sidebar from '../components/layout/Sidebar';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import StatusDot from '../components/ui/StatusDot';
import Alert from '../components/ui/Alert';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import DetectionChart from '../components/charts/DetectionChart';
import { useHealth } from '../hooks/useHealth';
import { useDetections } from '../hooks/useDetections';
import { useSignals } from '../hooks/useSignals';
import { useEvents } from '../hooks/useEvents';
import { formatRelativeTime, formatUptime, formatCurrentTime } from '../utils/format';
import { getModelInfo } from '../api/health';
import { useAuth } from '../auth/AuthContext';
import { useRequests } from '../hooks/useRequests';

const STATE_COLOR_MAP = {
  NORMAL: 'bg-green-100 border-green-300 text-green-900',
  SUSPECTED: 'bg-amber-100 border-amber-300 text-amber-900',
  CONFIRMED: 'bg-amber-100 border-amber-300 text-amber-900',
  PREPARING: 'bg-orange-100 border-orange-300 text-orange-900',
  SERVING: 'bg-red-100 border-red-300 text-red-900',
  RECOVERING: 'bg-emerald-100 border-emerald-300 text-emerald-900',
};

const STATE_DOT_COLOR = {
  NORMAL: 'green',
  SUSPECTED: 'amber',
  CONFIRMED: 'amber',
  PREPARING: 'amber',
  SERVING: 'red',
  RECOVERING: 'green',
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

function StatCard({ label, value, sub, loading, icon: Icon }) {
  return (
    <Card className="relative overflow-hidden">
      <div aria-hidden="true" className="absolute -right-4 -top-4 z-0 w-16 h-16 rounded-full bg-emerald-50" />
      <div className="relative z-10 flex items-start justify-between gap-3">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">{label}</p>
        {Icon && <span className="grid place-items-center w-8 h-8 rounded-lg bg-emerald-50 text-[#087f5b]"><Icon className="w-4 h-4" /></span>}
      </div>
      {loading ? (
        <div className="relative z-10 h-8 w-16 bg-gray-100 rounded animate-pulse" />
      ) : (
        <p className="relative z-10 text-3xl font-extrabold text-gray-900">{value ?? '—'}</p>
      )}
      {sub && <p className="relative z-10 text-xs text-gray-400 mt-1">{sub}</p>}
    </Card>
  );
}

function DispatcherDashboard() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [currentTime, setCurrentTime] = useState(formatCurrentTime());
  const [modelInfo, setModelInfo] = useState(null);
  const { user } = useAuth();

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
    <div className="ops-page min-h-screen bg-[#F6F8F7] flex">
      <Sidebar mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} />

      <div className="flex-1 lg:pl-64 flex flex-col">
        {/* Top bar */}
        <header className="ops-header sticky top-0 z-20 bg-white border-b border-gray-200 px-4 sm:px-6 py-3 flex items-center gap-3">
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
          <button
            onClick={refetch}
            className="p-2 rounded-md hover:bg-gray-100 text-gray-500"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </header>

        <main className="flex-1 p-4 sm:p-6 lg:p-8 space-y-6">
          {user?.role === 'AMBULANCE' && <section className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 sm:flex sm:items-center sm:justify-between"><div><p className="text-xs font-bold uppercase tracking-wide text-emerald-700">Registered ambulance</p><p className="mt-1 font-mono text-xl font-extrabold text-emerald-950">{user.ambulance?.lifelane_id || 'Linked ambulance unavailable'}</p></div><div className="mt-3 text-sm text-emerald-900 sm:mt-0 sm:text-right"><b>{user.ambulance?.service_name}</b><br />{user.ambulance?.registration_number}</div></section>}
          <section className="emerald-panel relative overflow-hidden rounded-3xl px-5 py-6 sm:px-7 sm:py-7">
            <div className="absolute -right-16 -top-20 w-64 h-64 rounded-full border border-white/15" />
            <div className="absolute right-10 bottom-0 w-32 h-32 rounded-full bg-emerald-300/10 blur-2xl" />
            <div className="relative flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p className="text-[11px] font-bold uppercase tracking-[.18em] text-emerald-100">Emergency mobility coordination</p>
                <h2 className="mt-2 text-2xl sm:text-3xl font-extrabold tracking-tight">Simulation operations center</h2>
                <p className="mt-2 max-w-xl text-sm text-emerald-100/85">Monitor verified audio events and traffic-priority simulation activity across the LifeLane network.</p>
              </div>
              <div className="flex items-center gap-3 rounded-2xl border border-white/15 bg-emerald-950/20 px-4 py-3 backdrop-blur-sm">
                <span className={`w-2.5 h-2.5 rounded-full ${online ? 'bg-emerald-300 shadow-[0_0_12px_#6ee7b7]' : 'bg-amber-300'}`} />
                <div><p className="text-[10px] uppercase tracking-wider text-emerald-100/70">Service status</p><p className="text-sm font-bold">{online ? 'System connected' : 'Checking service'}</p></div>
              </div>
            </div>
          </section>
          {/* Backend status */}
          {online === false && (
            <Alert variant="error" title="Backend Offline">
              Cannot connect to backend at http://localhost:8000. {healthError}
              <button onClick={refetch} className="ml-2 underline text-xs">Retry</button>
            </Alert>
          )}
          {online === true && (
            <div className="system-online flex items-center gap-2 text-sm rounded-lg px-4 py-2">
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
              icon={Activity}
            />
            <StatCard
              label="Total Detections"
              value={stats?.total_detections ?? (online === false ? '—' : '...')}
              sub="All time"
              loading={online === null}
              icon={Radio}
            />
            <StatCard
              label="Active Requests"
              value={stats?.active_requests ?? '—'}
              sub="In progress"
              loading={online === null}
              icon={Activity}
            />
            <StatCard
              label="Junctions Serving"
              value={stats?.junctions_serving ?? '—'}
              sub="Of 4 total"
              loading={online === null}
              icon={MapPinned}
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
            <div className="flex items-end justify-between mb-3"><div><p className="section-eyebrow">Network view</p><h2 className="mt-1 text-lg font-bold text-gray-900">Junction status</h2></div><span className="text-xs text-gray-400">Live controller state</span></div>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {junctions.map((j) => (
                <JunctionCard key={j.junction_id || j.id} junction={j} />
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            {/* Detection chart */}
            <Card>
              <p className="section-eyebrow">Recognition intelligence</p><h2 className="mt-1 text-lg font-bold text-gray-900 mb-4">Detection overview</h2>
              {detectLoading ? <LoadingSpinner /> : <DetectionChart detections={detections} />}
            </Card>

            {/* Recent events */}
            <Card>
              <p className="section-eyebrow">Activity stream</p><h2 className="mt-1 text-lg font-bold text-gray-900 mb-4">Recent events</h2>
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

function AmbulanceDashboard({ user }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { requests, loading, error, refetch } = useRequests(10000);
  const counts = ['PENDING', 'ACTIVE', 'COMPLETED'].map((status) => ({ status, value: requests.filter((request) => request.status === status).length }));
  return <div className="ops-page min-h-screen bg-[#F6F8F7] flex"><Sidebar mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} /><div className="flex-1 lg:pl-64"><header className="ops-header sticky top-0 z-20 flex items-center gap-3 border-b border-gray-200 bg-white px-4 py-3 sm:px-6"><button className="lg:hidden p-2 rounded-md hover:bg-gray-100" onClick={() => setMobileOpen(true)} aria-label="Open menu"><Menu className="w-5 h-5 text-gray-600" /></button><div className="flex-1"><h1 className="font-bold text-gray-900 text-lg">Ambulance dashboard</h1><p className="text-xs text-gray-500">Your identity and emergency requests</p></div><button onClick={refetch} className="p-2 rounded-md hover:bg-gray-100 text-gray-500" title="Refresh"><RefreshCw className="w-4 h-4" /></button></header><main className="space-y-6 p-4 sm:p-6"><section className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5"><p className="text-xs font-bold uppercase tracking-wide text-emerald-700">Your LifeLane ID</p><p className="mt-1 font-mono text-2xl font-extrabold text-emerald-950">{user.ambulance?.lifelane_id}</p><dl className="mt-4 grid gap-3 text-sm sm:grid-cols-3"><div><dt className="text-gray-500">Organization</dt><dd className="font-semibold">{user.ambulance?.service_name}</dd></div><div><dt className="text-gray-500">Vehicle registration</dt><dd className="font-semibold">{user.ambulance?.registration_number}</dd></div><div><dt className="text-gray-500">Contact</dt><dd className="font-semibold">{user.ambulance?.contact_name}</dd></div></dl></section><section className="grid grid-cols-3 gap-4">{counts.map(({ status, value }) => <Card key={status} className="text-center"><p className="text-xs font-semibold text-gray-500">{status}</p><p className="mt-1 text-3xl font-extrabold text-gray-900">{value}</p></Card>)}</section><Card><div className="flex items-center justify-between"><div><p className="section-eyebrow">Request history</p><h2 className="mt-1 text-lg font-bold text-gray-900">Your emergency requests</h2></div><button onClick={refetch} className="text-sm font-semibold text-[#087f5b]">Refresh</button></div>{error && <p className="mt-4 text-sm text-red-700">{error}</p>}{loading ? <LoadingSpinner /> : requests.length === 0 ? <p className="py-8 text-sm text-gray-500">No emergency requests yet.</p> : <div className="mt-4 divide-y divide-gray-100">{requests.map((request) => <div key={request.id} className="flex flex-wrap items-center justify-between gap-3 py-3 text-sm"><div><p className="font-mono font-bold text-[#087f5b]">{request.request_id}</p><p className="text-gray-500">{request.hospital_id} · {request.junction_id}</p></div><Badge state={request.status}>{request.status}</Badge></div>)}</div>}</Card></main></div></div>;
}

export default function Dashboard() {
  const { user } = useAuth();
  return user?.role === 'AMBULANCE' ? <AmbulanceDashboard user={user} /> : <DispatcherDashboard />;
}
