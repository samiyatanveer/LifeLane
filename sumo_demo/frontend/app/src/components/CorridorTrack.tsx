// CorridorTrack.tsx
import type { Snapshot } from '../types';
import { X, END, ER_X } from '../mock/MockSource';

interface Props { snapshot: Snapshot; }

export default function CorridorTrack({ snapshot }: Props) {
  const A = snapshot.ambulance;
  const done = A?.done;
  const f = A ? Math.min(1, A.s / ER_X) : 0;
  const ambPct = f * (ER_X / END) * 100;

  let etaText = 'idle – press Dispatch';
  if (A) {
    if (done) {
      etaText = `arrived in ${A.elapsed.toFixed(1)}s`;
    } else {
      const rem = Math.max(0, ER_X - A.s);
      const eta = (rem / 15 + (snapshot.preempt ? 0 : 6)).toFixed(0);
      etaText = `${Math.round(rem)} m to ER · ETA ${eta}s`;
    }
  }

  return (
    <div className="card">
      <h3>
        Corridor{' '}
        <span style={{ textTransform:'none', letterSpacing:0, color:'#c9d6ec' }}>{etaText}</span>
      </h3>
      <div style={{ position:'relative', height:46, margin:'2px 6px 0' }}>
        {/* base line */}
        <div style={{ position:'absolute', left:0, right:0, top:20, height:6, borderRadius:3, background:'#1b2740' }} />
        {/* progress */}
        <div style={{
          position:'absolute', left:0, top:20, height:6, borderRadius:3,
          background:'linear-gradient(90deg,#22c55e,#38bdf8)',
          width: A ? ambPct + '%' : '0',
          transition:'width 0.1s',
        }} />
        {/* junction dots */}
        {X.map((x, j) => {
          const jn = snapshot.junctions[j];
          const col = jn ? ({ NORMAL:'#8a9bb8', PREPARING:'#f59e0b', SERVING:'#22c55e', RECOVERING:'#38bdf8' }[jn.mode]) : '#8a9bb8';
          return (
            <div key={j} style={{
              position:'absolute', top:11, width:24, height:24,
              marginLeft:-12, left: x/END*100+'%',
              borderRadius:'50%', background:'#101a2b', border:`2px solid ${col}`,
              display:'grid', placeItems:'center',
              fontSize:10, fontWeight:700, fontFamily:'var(--mono)', color: col,
            }}>J{j+1}</div>
          );
        })}
        {/* hospital H */}
        <div style={{
          position:'absolute', top:9, right:-8, width:28, height:28, borderRadius:8,
          background:'#ef4444', display:'grid', placeItems:'center',
          fontWeight:800, color:'#fff', boxShadow:'0 0 14px rgba(239,68,68,.5)',
        }}>H</div>
        {/* ambulance dot */}
        {A && !done && (
          <div style={{
            position:'absolute', top:2, width:18, height:18, marginLeft:-9,
            left: ambPct + '%',
            borderRadius:'50%', background:'#fff',
            boxShadow:'0 0 0 3px rgba(239,68,68,.5), 0 0 14px #ef4444',
            transition:'left 0.1s',
          }} />
        )}
      </div>
    </div>
  );
}
