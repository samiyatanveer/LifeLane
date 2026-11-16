import React, { useState } from 'react';
import { useSignals } from '../hooks/useSignals';
import { useEvents } from '../hooks/useEvents';
import { simulateSignal } from '../api/signals';
import { getStats } from '../api/health';

export default function SignalsOps() {
  const { signals, loading: signalsLoading, refresh: refreshSignals } = useSignals(3000);
  const { events, refresh: refreshEvents } = useEvents(3000);
  const [stats, setStats] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [message, setMessage] = useState('');

  // Fetch stats periodically
  React.useEffect(() => {
    let mounted = true;
    const fetchStats = async () => {
      try {
        const s = await getStats();
        if (mounted) setStats(s);
      } catch {
        // quiet fallback
      }
    };
    fetchStats();
    const interval = setInterval(fetchStats, 5000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  const handleSimulate = async (junctionId, action, extra = {}) => {
    setActionLoading(true);
    setMessage('');
    try {
      const res = await simulateSignal(junctionId, action, extra);
      setMessage(`Junction ${junctionId}: State updated to ${res.state}`);
      await refreshSignals();
      await refreshEvents();
    } catch (err) {
      setMessage(`Error: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const getStatusClass = (state) => {
    switch (state) {
      case 'SERVING': return 'border-[var(--red)] bg-red-500/10 text-[var(--red)]';
      case 'PREPARING': return 'border-[var(--amber)] bg-amber-500/10 text-[var(--amber)]';
      case 'RECOVERING': return 'border-blue-500 bg-blue-500/10 text-blue-700';
      default: return 'border-[var(--g2)] bg-[var(--tint)] text-[var(--g2)]';
    }
  };

  return (
    <section className="py-12 wrap">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-2">
        <h2>Live signal preemption controller</h2>
        <span className="status-pill alert">
          <s />
          <span>Simulation Safety Boundary</span>
        </span>
      </div>
      <p className="mb-8">
        Directly monitor and test the 4-junction corridor (J1–J4). Experience how the independent Safety Controller enforces clearances, yellow intervals, and bounded recovery.
      </p>

      {/* Stats Row */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
          <div className="life-card p-4">
            <span className="block text-2xl font-black text-[var(--g2)]" style={{ fontFamily: '"Bricolage Grotesque", sans-serif' }}>
              {stats.total_detections}
            </span>
            <small className="text-xs text-[var(--mute)]">Total Acoustic Checks</small>
          </div>
          <div className="life-card p-4">
            <span className="block text-2xl font-black text-[var(--red)]" style={{ fontFamily: '"Bricolage Grotesque", sans-serif' }}>
              {stats.siren_detections}
            </span>
            <small className="text-xs text-[var(--mute)]">Siren Events Confirmed</small>
          </div>
          <div className="life-card p-4">
            <span className="block text-2xl font-black text-[var(--gold)]" style={{ fontFamily: '"Bricolage Grotesque", sans-serif' }}>
              {stats.total_ambulances || 3}
            </span>
            <small className="text-xs text-[var(--mute)]">Registered Ambulances</small>
          </div>
          <div className="life-card p-4">
            <span className="block text-2xl font-black text-[var(--ink)]" style={{ fontFamily: '"Bricolage Grotesque", sans-serif' }}>
              {stats.signal_events || 0}
            </span>
            <small className="text-xs text-[var(--mute)]">Signal Transitions Logged</small>
          </div>
        </div>
      )}

      {message && (
        <div className="mb-6 p-3 rounded-xl bg-[var(--tint)] text-[var(--ink)] text-xs font-bold border border-[var(--line)]">
          {message}
        </div>
      )}

      {/* 4-Junction Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {(signals || [
          { junction_id: 'J1', state: 'NORMAL' },
          { junction_id: 'J2', state: 'NORMAL' },
          { junction_id: 'J3', state: 'NORMAL' },
          { junction_id: 'J4', state: 'NORMAL' },
        ]).map((j) => (
          <div key={j.junction_id} className="life-card flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-3">
                <span className="font-extrabold text-xl" style={{ fontFamily: '"Bricolage Grotesque", sans-serif' }}>
                  Junction {j.junction_id}
                </span>
                <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold border ${getStatusClass(j.state)}`}>
                  {j.state}
                </span>
              </div>

              <div className="text-xs text-[var(--mute)] mb-4 space-y-1">
                <div>Serving Approach: <strong>{j.approach || 'None (Cycle)'}</strong></div>
                <div>Ambulance ID: <strong>{j.ambulance_id || 'None'}</strong></div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex flex-col gap-2 pt-3 border-t border-[var(--line)]">
              {j.state === 'NORMAL' && (
                <button
                  disabled={actionLoading}
                  onClick={() => handleSimulate(j.junction_id, 'request_priority', { approach: 'north', ambulance_id: 'LL-AMB-01' })}
                  className="cta-btn text-xs py-2 w-full"
                >
                  Request Preemption
                </button>
              )}

              {j.state === 'SERVING' && (
                <button
                  disabled={actionLoading}
                  onClick={() => handleSimulate(j.junction_id, 'confirm_passage')}
                  className="cta-btn alt text-xs py-2 w-full"
                  style={{ backgroundColor: '#22B866', color: '#ffffff' }}
                >
                  Confirm Passage (Exit)
                </button>
              )}

              {j.state !== 'NORMAL' && (
                <button
                  disabled={actionLoading}
                  onClick={() => handleSimulate(j.junction_id, 'reset')}
                  className="cta-btn alt text-xs py-1.5 w-full text-[var(--red)]"
                >
                  Cancel / Reset
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Real Audit Event Log */}
      <div className="mt-10 life-card p-5">
        <h3 className="text-base mb-1">Live signal event audit trail</h3>
        <p className="text-xs mb-4 text-[var(--mute)]">
          Real-time record of all state transitions stored in SQLite database.
        </p>

        <div className="max-h-56 overflow-y-auto divide-y divide-[var(--line)]">
          {events && events.length > 0 ? (
            events.slice(0, 8).map((ev) => (
              <div key={ev.id} className="py-2.5 flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-[var(--ink)]">{ev.junction_id}</span>
                  <span className="text-[var(--mute)]">
                    {ev.from_state} &rarr; <strong className="text-[var(--g2)]">{ev.to_state}</strong>
                  </span>
                  <span className="px-2 py-0.5 rounded-full bg-[var(--tint)] text-[10px] font-semibold text-[var(--mute)]">
                    Trigger: {ev.trigger}
                  </span>
                </div>
                <span className="text-[11px] text-[var(--mute)]">
                  {new Date(ev.created_at).toLocaleTimeString()}
                </span>
              </div>
            ))
          ) : (
            <div className="py-6 text-center text-xs text-[var(--mute)]">
              No recent events. Click "Request Preemption" above to simulate an emergency corridor action.
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
