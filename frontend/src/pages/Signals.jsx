import { useState } from 'react';
import { Menu, TrafficCone, ShieldAlert, CheckCircle, RefreshCw, Play, Check, RotateCcw } from 'lucide-react';
import Sidebar from '../components/layout/Sidebar';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';
import Alert from '../components/ui/Alert';
import SimulationBadge from '../components/ui/SimulationBadge';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import StatusDot from '../components/ui/StatusDot';
import { useSignals } from '../hooks/useSignals';
import { useEvents } from '../hooks/useEvents';
import { simulateSignal } from '../api/signals';
import { formatTimestamp } from '../utils/format';
import { APPROACHES, SAFETY_RULES } from '../utils/constants';

const STATE_CONFIG = {
  NORMAL: {
    bg: 'bg-green-50 border-green-300 text-green-900',
    dot: 'green',
    label: 'NORMAL',
  },
  SUSPECTED: {
    bg: 'bg-amber-50 border-amber-300 text-amber-900',
    dot: 'amber',
    label: 'SUSPECTED',
  },
  CONFIRMED: {
    bg: 'bg-amber-50 border-amber-300 text-amber-900',
    dot: 'amber',
    label: 'CONFIRMED',
  },
  PREPARING: {
    bg: 'bg-orange-50 border-orange-300 text-orange-900',
    dot: 'amber',
    label: 'PREPARING',
  },
  SERVING: {
    bg: 'bg-red-50 border-red-400 text-red-900',
    dot: 'red',
    label: 'SERVING',
  },
  RECOVERING: {
    bg: 'bg-blue-50 border-blue-300 text-blue-900',
    dot: 'blue',
    label: 'RECOVERING',
  },
};

export default function Signals() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [actionLoading, setActionLoading] = useState({});
  const [actionError, setActionError] = useState(null);
  const [activeFormJunction, setActiveFormJunction] = useState(null);
  const [formApproach, setFormApproach] = useState('north');
  const [formAmbulanceId, setFormAmbulanceId] = useState('AMB-01');

  const { signals, loading: signalsLoading, error: signalsError, refetch: refetchSignals } = useSignals(4000);
  const { events, loading: eventsLoading, refetch: refetchEvents } = useEvents(15, 4000);

  const handleSimulate = async (junctionId, action, extra = {}) => {
    setActionLoading((prev) => ({ ...prev, [junctionId]: action }));
    setActionError(null);
    try {
      await simulateSignal(junctionId, action, extra);
      if (activeFormJunction === junctionId) {
        setActiveFormJunction(null);
      }
      await Promise.all([refetchSignals(), refetchEvents()]);
    } catch (err) {
      setActionError(`[${junctionId}] Simulation failed: ${err.message}`);
    } finally {
      setActionLoading((prev) => ({ ...prev, [junctionId]: null }));
    }
  };

  const signalMap = {};
  signals.forEach((s) => {
    signalMap[s.junction_id || s.id] = s;
  });

  const junctionList = ['J1', 'J2', 'J3', 'J4'].map((id) => {
    return signalMap[id] || { junction_id: id, id, state: 'NORMAL', time_in_state: 0 };
  });

  return (
    <div className="min-h-screen bg-[#F6F8F7] flex">
      <Sidebar mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} />

      <div className="flex-1 lg:pl-64 flex flex-col">
        {/* Top Header */}
        <header className="sticky top-0 z-20 bg-white border-b border-gray-200 px-4 sm:px-6 py-3 flex items-center gap-3">
          <button
            className="lg:hidden p-2 rounded-md hover:bg-gray-100"
            onClick={() => setMobileOpen(true)}
            aria-label="Open menu"
          >
            <Menu className="w-5 h-5 text-gray-600" />
          </button>
          <TrafficCone className="w-5 h-5 text-[#087F5B]" />
          <div className="flex-1 min-w-0">
            <h1 className="font-bold text-gray-900 text-lg truncate">Signal Control Simulation</h1>
          </div>
          <SimulationBadge />
          <button
            onClick={() => { refetchSignals(); refetchEvents(); }}
            className="p-2 rounded-md hover:bg-gray-100 text-gray-500"
            title="Refresh signals"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </header>

        <main className="flex-1 p-4 sm:p-6 space-y-6">
          {/* Always Visible Safety Disclaimer */}
          <div className="bg-amber-50 border-2 border-amber-300 rounded-xl p-4 flex items-start gap-3 text-amber-900 shadow-sm">
            <ShieldAlert className="w-6 h-6 text-amber-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm">
              <span className="font-bold tracking-wide uppercase block text-amber-800 mb-0.5">
                Simulation Disclaimer
              </span>
              SIMULATION ONLY — This panel simulates signal behavior. It never controls real traffic signals. All actions interact exclusively with the local SUMO-compatible simulation engine.
            </div>
          </div>

          {signalsError && (
            <Alert variant="error" title="Connection Error">
              Cannot connect to backend: {signalsError}
            </Alert>
          )}

          {actionError && (
            <Alert variant="error" dismissible onClose={() => setActionError(null)}>
              {actionError}
            </Alert>
          )}

          {/* Junction Grid */}
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold text-gray-700 uppercase tracking-wider">
                Junction Controllers (4 Nodes)
              </h2>
              {signalsLoading && <LoadingSpinner size="sm" />}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {junctionList.map((junc) => {
                const jId = junc.junction_id || junc.id;
                const state = junc.state || 'NORMAL';
                const cfg = STATE_CONFIG[state] || STATE_CONFIG.NORMAL;
                const isServing = state === 'SERVING';
                const canRequest = ['NORMAL', 'SUSPECTED', 'CONFIRMED'].includes(state);
                const canConfirm = state === 'SERVING';
                const currentAction = actionLoading[jId];

                return (
                  <div
                    key={jId}
                    className={`rounded-2xl border-2 p-5 ${cfg.bg} transition-all duration-300 ${
                      isServing ? 'ring-4 ring-red-400 ring-offset-2 animate-pulse' : 'shadow-sm'
                    }`}
                  >
                    <div className="flex items-center justify-between border-b border-gray-200/60 pb-3 mb-3">
                      <div className="flex items-center gap-2">
                        <span className="text-xl font-extrabold text-gray-900 tracking-tight">{jId}</span>
                        <span className="text-xs text-gray-500 font-medium">Junction Controller</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <StatusDot color={cfg.dot} animate={isServing} size="md" />
                        <Badge state={state}>{state}</Badge>
                      </div>
                    </div>

                    {/* Metadata details */}
                    <div className="grid grid-cols-3 gap-2 text-xs py-2 bg-white/70 rounded-lg px-3 mb-4">
                      <div>
                        <span className="text-gray-500 block">Approach:</span>
                        <span className="font-semibold text-gray-800 capitalize">
                          {junc.approach || '—'}
                        </span>
                      </div>
                      <div>
                        <span className="text-gray-500 block">Ambulance:</span>
                        <span className="font-semibold text-gray-800">
                          {junc.ambulance_id || '—'}
                        </span>
                      </div>
                      <div>
                        <span className="text-gray-500 block">Time in State:</span>
                        <span className="font-semibold text-gray-800">
                          {junc.time_in_state ? `${junc.time_in_state}s` : '0s'}
                        </span>
                      </div>
                    </div>

                    {/* Mini Form for Request Priority */}
                    {activeFormJunction === jId && (
                      <div className="bg-white p-3 rounded-lg border border-gray-300 mb-4 space-y-3">
                        <p className="text-xs font-bold text-gray-700 uppercase">
                          Simulation: Request Signal Priority
                        </p>
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          <div>
                            <label className="block text-gray-500 mb-1">Approach</label>
                            <select
                              value={formApproach}
                              onChange={(e) => setFormApproach(e.target.value)}
                              className="w-full border border-gray-300 rounded px-2 py-1 bg-white"
                            >
                              {APPROACHES.map((a) => (
                                <option key={a.value} value={a.value}>{a.label}</option>
                              ))}
                            </select>
                          </div>
                          <div>
                            <label className="block text-gray-500 mb-1">Ambulance ID</label>
                            <input
                              type="text"
                              value={formAmbulanceId}
                              onChange={(e) => setFormAmbulanceId(e.target.value)}
                              className="w-full border border-gray-300 rounded px-2 py-1"
                              placeholder="e.g. AMB-01"
                            />
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            loading={currentAction === 'request_priority'}
                            onClick={() =>
                              handleSimulate(jId, 'request_priority', {
                                approach: formApproach,
                                ambulance_id: formAmbulanceId,
                              })
                            }
                          >
                            Send SIMULATION Action
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => setActiveFormJunction(null)}
                          >
                            Cancel
                          </Button>
                        </div>
                      </div>
                    )}

                    {/* Action Buttons */}
                    <div className="space-y-2">
                      <div className="flex flex-wrap gap-2">
                        <button
                          disabled={!canRequest || currentAction}
                          onClick={() => {
                            if (activeFormJunction === jId) {
                              setActiveFormJunction(null);
                            } else {
                              setActiveFormJunction(jId);
                            }
                          }}
                          className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-lg border transition-all ${
                            canRequest && !currentAction
                              ? 'bg-[#087F5B] hover:bg-[#0B5D3B] text-white border-transparent cursor-pointer'
                              : 'bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed'
                          }`}
                        >
                          <Play className="w-3.5 h-3.5" />
                          <span>Request Priority</span>
                          <span className="text-[10px] opacity-75">(SIMULATION)</span>
                        </button>

                        <button
                          disabled={!canConfirm || currentAction}
                          onClick={() => handleSimulate(jId, 'confirm_passage')}
                          className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-lg border transition-all ${
                            canConfirm && !currentAction
                              ? 'bg-blue-600 hover:bg-blue-700 text-white border-transparent cursor-pointer'
                              : 'bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed'
                          }`}
                        >
                          <Check className="w-3.5 h-3.5" />
                          <span>Confirm Passage</span>
                          <span className="text-[10px] opacity-75">(SIMULATION)</span>
                        </button>
                      </div>

                      <button
                        disabled={currentAction}
                        onClick={() => handleSimulate(jId, 'reset')}
                        className="w-full flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600 hover:text-gray-900 bg-white/80 hover:bg-white border border-gray-300 rounded-lg transition-colors cursor-pointer"
                      >
                        <RotateCcw className="w-3 h-3 text-gray-500" />
                        <span>Cancel / Reset Signal</span>
                        <span className="text-[10px] text-gray-400 font-normal">[SIMULATION ACTION]</span>
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Safety Rules Info Box */}
          <Card>
            <div className="flex items-center gap-2 mb-3">
              <CheckCircle className="w-5 h-5 text-[#087F5B]" />
              <h3 className="font-bold text-gray-900 text-sm">
                Safety Invariants: 6 Required Pre-Conditions
              </h3>
            </div>
            <p className="text-xs text-gray-500 mb-3">
              In a production system, all 6 invariants below must be strictly satisfied before any signal preemption is granted:
            </p>
            <ul className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {SAFETY_RULES.map((rule, idx) => (
                <li key={idx} className="flex items-start gap-2 text-xs text-gray-700 bg-gray-50 p-2.5 rounded-lg border border-gray-200">
                  <span className="font-bold text-[#087F5B]">{idx + 1}.</span>
                  <span>{rule}</span>
                </li>
              ))}
            </ul>
          </Card>

          {/* Signal Events Log */}
          <Card>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold text-gray-900 text-sm">
                Signal Transition Event Log (Last 15)
              </h3>
              <span className="text-xs text-gray-400">Simulation Logs</span>
            </div>

            {eventsLoading ? (
              <LoadingSpinner />
            ) : events.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-6">No signal events recorded yet</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-gray-200 text-gray-500 uppercase tracking-wider text-left">
                      <th className="pb-2 font-semibold">Time</th>
                      <th className="pb-2 font-semibold">Junction</th>
                      <th className="pb-2 font-semibold">Transition</th>
                      <th className="pb-2 font-semibold">Trigger</th>
                      <th className="pb-2 font-semibold">Ambulance</th>
                      <th className="pb-2 font-semibold">Type</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {events.slice(0, 15).map((ev, i) => (
                      <tr key={ev.id || i} className="hover:bg-gray-50">
                        <td className="py-2 text-gray-500 whitespace-nowrap">
                          {formatTimestamp(ev.created_at || ev.timestamp)}
                        </td>
                        <td className="py-2 font-bold text-gray-800">
                          {ev.junction_id || ev.junction || '—'}
                        </td>
                        <td className="py-2">
                          <div className="flex items-center gap-1">
                            <span className="font-semibold text-gray-600">{ev.from_state || '—'}</span>
                            <span className="text-gray-400">→</span>
                            <span className="font-bold text-primary">{ev.to_state || ev.state || '—'}</span>
                          </div>
                        </td>
                        <td className="py-2 text-gray-700">
                          {ev.trigger || ev.action || '—'}
                        </td>
                        <td className="py-2 text-gray-600">
                          {ev.ambulance_id || '—'}
                        </td>
                        <td className="py-2">
                          <span className="bg-red-50 text-red-700 border border-red-200 rounded px-1.5 py-0.5 text-[10px] font-bold">
                            SIMULATED
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </main>
      </div>
    </div>
  );
}
