// SafetyMonitor.tsx
import type { Snapshot } from '../types';

interface Props { snapshot: Snapshot; }

export default function SafetyMonitor({ snapshot }: Props) {
  const { safety, ambulance: A } = snapshot;
  const elapsed = A ? A.elapsed : 0;
  const stopped = A ? A.stopped_s : 0;
  const closest = A && safety.min_clearance_m != null ? safety.min_clearance_m.toFixed(1)+'m' : '–';

  const stats = [
    { label: 'Elapsed',      val: elapsed.toFixed(1)+'s' },
    { label: 'Amb. stopped', val: stopped.toFixed(1)+'s' },
    { label: 'Held at red',  val: String(safety.held_at_red) },
    { label: 'Max open',     val: String(safety.max_open) },
    { label: 'Collisions',   val: String(safety.collisions) },
    { label: 'Closest',      val: closest },
  ];

  return (
    <div className="card">
      <h3>Safety monitor</h3>
      <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:8 }}>
        {stats.map(({ label, val }) => (
          <div key={label} style={{
            background:'#0d1626', border:'1px solid var(--line)',
            borderRadius:10, padding:'7px 9px',
          }}>
            <small style={{ display:'block', color:'var(--mute)', fontSize:10.5, letterSpacing:'.5px', textTransform:'uppercase' }}>
              {label}
            </small>
            <b style={{ fontFamily:'var(--mono)', fontSize:17 }}>{val}</b>
          </div>
        ))}
      </div>
    </div>
  );
}
