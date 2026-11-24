// JunctionCard.tsx
import type { Junction } from '../types';

const MODE_COL = { NORMAL:'#8a9bb8', PREPARING:'#f59e0b', SERVING:'#22c55e', RECOVERING:'#38bdf8' };
const SIG_COL  = { R:'#ef4444', Y:'#f59e0b', G:'#22c55e' };

interface Props { junctions: Junction[]; }

export default function JunctionCard({ junctions }: Props) {
  return (
    <div className="card">
      <h3>Junction controllers <span style={{ textTransform:'none', letterSpacing:0 }}>W · N · E · S</span></h3>
      {junctions.map((jn, j) => {
        const mc = MODE_COL[jn.mode];
        return (
          <div key={jn.id} style={{
            display:'grid', gridTemplateColumns:'1fr auto', gap:'6px 8px',
            alignItems:'center', padding:'9px 0',
            borderTop: j === 0 ? 'none' : '1px solid var(--line)',
          }}>
            {/* name + pill */}
            <div style={{ fontWeight:700, display:'flex', gap:8, alignItems:'center' }}>
              {jn.id}
              <span style={{
                padding:'2px 9px', borderRadius:999, fontSize:11, fontWeight:700,
                letterSpacing:'.4px', border:`1px solid ${mc}`, color:mc, background:mc+'22',
              }}>{jn.mode}</span>
            </div>
            {/* approach boxes */}
            <div style={{ display:'flex', gap:5 }}>
              {(['W','N','E','S'] as const).map(ap => {
                const st = jn.lights[ap];
                const bg = SIG_COL[st] + (st==='R'?'99':'');
                return (
                  <div key={ap} style={{
                    width:30, textAlign:'center', borderRadius:7, fontSize:10.5,
                    fontWeight:700, padding:'2px 0', color:'#fff',
                    border:'1px solid rgba(255,255,255,.08)',
                    background: bg,
                    boxShadow: st==='G'?'0 0 10px #22c55e':'none',
                    transition:'background 0.3s, box-shadow 0.3s',
                  }}>{ap}</div>
                );
              })}
            </div>
            {/* acoustic bar + tiers */}
            <div style={{ gridColumn:'1/3', display:'flex', gap:8, alignItems:'center', fontSize:11.5, color:'var(--mute)' }}>
              <span>🎙</span>
              <div className="pbar">
                <div className="pbar-fill" style={{ width:(jn.acoustic.p*100)+'%' }} />
                <div className="pbar-thresh" />
              </div>
              {(['t1','t2','t3'] as const).map((tk, i) => {
                const on = i===0?jn.acoustic.tier1 : i===1?jn.tier2_route : jn.tier3_gps;
                return (
                  <span key={tk} className={`tk ${on?'y':''}`}>T{i+1}</span>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
