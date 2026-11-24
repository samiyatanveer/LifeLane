// Header.tsx
import type { Snapshot } from '../types';

interface Props { snapshot: Snapshot; }

export default function Header({ snapshot }: Props) {
  const { safety, preempt, demoData } = snapshot;
  const oneOk = safety.max_open <= 1;
  const colOk = safety.collisions === 0;

  return (
    <header style={{
      display:'flex', alignItems:'center', gap:14, padding:'10px 16px',
      borderBottom:'1px solid var(--line)',
      background:'linear-gradient(180deg,#0e1830,#0a101c)',
      flexWrap:'wrap',
    }}>
      <div style={{ display:'flex', alignItems:'center', gap:10, fontWeight:700, letterSpacing:'.2px' }}>
        <i style={{
          width:30, height:30, borderRadius:9, background:'linear-gradient(135deg,#22c55e,#38bdf8)',
          display:'grid', placeItems:'center', color:'#06210f', fontStyle:'normal', fontWeight:800,
          boxShadow:'0 0 18px rgba(34,197,94,.35)',
        }}>L</i>
        <div>
          LifeLane
          <small style={{ display:'block', color:'var(--mute)', fontWeight:500, fontSize:11, letterSpacing:'.4px' }}>
            EMERGENCY GREEN-CORRIDOR · LIVE DEMO
          </small>
        </div>
      </div>

      <div style={{ display:'flex', gap:8, marginLeft:'auto', flexWrap:'wrap' }}>
        {demoData && (
          <div className="chip" style={{ borderColor:'rgba(167,139,250,.5)', color:'#c4b5fd' }}>
            DEMO DATA
          </div>
        )}
        <div className={`chip ${oneOk ? 'ok' : 'bad'}`}>
          ONE OPEN / JUNCTION <b>{oneOk ? '✓' : '✗'}</b>
        </div>
        <div className={`chip ${colOk ? 'ok' : 'bad'}`}>
          COLLISIONS <b>{safety.collisions}</b>
        </div>
        <div className="chip">
          LIFELANE <b>{preempt ? 'ON' : 'OFF'}</b>
        </div>
      </div>
    </header>
  );
}
