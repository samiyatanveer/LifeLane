// ModelPanel.tsx – NEW panel: acoustic charts, ETA predictions, A/B impact, model health
import type { Snapshot } from '../types';
import {
  LineChart, Line, XAxis, YAxis, ReferenceLine, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell,
} from 'recharts';

interface Props { snapshot: Snapshot; history: Snapshot[]; }

const MODE_COL = { NORMAL:'#8a9bb8', PREPARING:'#f59e0b', SERVING:'#22c55e', RECOVERING:'#38bdf8' };

export default function ModelPanel({ snapshot, history }: Props) {
  const { junctions, predictions, result, safety } = snapshot;

  // Build acoustic history from last N snapshots
  const acousticData = history.slice(-60).map((s, i) => ({
    i,
    J1: s.junctions[0]?.acoustic.p ?? 0,
    J2: s.junctions[1]?.acoustic.p ?? 0,
    J3: s.junctions[2]?.acoustic.p ?? 0,
  }));

  // ETA table data
  const etaRows = predictions.eta.map(e => ({
    junction: e.junction,
    predicted: e.predicted_s != null ? e.predicted_s.toFixed(1) : '–',
    actual: e.actual_s != null ? e.actual_s.toFixed(1) : '–',
    error: (e.predicted_s != null && e.actual_s != null)
      ? Math.abs(e.predicted_s - e.actual_s).toFixed(1)
      : '–',
  }));

  return (
    <div style={{ display:'flex', flexDirection:'column', gap:10 }}>
      {/* ---- Acoustic Siren Probability ---- */}
      <div className="card">
        <h3>Acoustic · siren probability per junction</h3>
        <ResponsiveContainer width="100%" height={90}>
          <LineChart data={acousticData} margin={{ top:4, right:4, left:-20, bottom:0 }}>
            <XAxis dataKey="i" hide />
            <YAxis domain={[0,1]} tickCount={3} style={{ fontSize:9, fill:'#8a9bb8' }} />
            <ReferenceLine y={0.70} stroke="#f59e0b" strokeDasharray="4 2" />
            <Tooltip
              contentStyle={{ background:'#0d1626', border:'1px solid #1d2a44', borderRadius:8, fontSize:11 }}
              labelStyle={{ color:'#8a9bb8' }}
            />
            <Line type="monotone" dataKey="J1" stroke="#22c55e" dot={false} strokeWidth={1.5} />
            <Line type="monotone" dataKey="J2" stroke="#38bdf8" dot={false} strokeWidth={1.5} />
            <Line type="monotone" dataKey="J3" stroke="#a78bfa" dot={false} strokeWidth={1.5} />
          </LineChart>
        </ResponsiveContainer>
        <div style={{ display:'flex', gap:10, marginTop:4, fontSize:11, color:'#8a9bb8' }}>
          {['J1','J2','J3'].map((id, i) => {
            const cols=['#22c55e','#38bdf8','#a78bfa'];
            const jn = junctions[i];
            return (
              <span key={id} style={{ display:'flex', alignItems:'center', gap:4 }}>
                <span style={{ width:10, height:3, background:cols[i], borderRadius:2, display:'inline-block' }} />
                {id}: <b style={{ color:cols[i], fontFamily:'var(--mono)' }}>{(jn?.acoustic.p??0).toFixed(2)}</b>
                {jn?.acoustic.tier1 && <span className="tk y" style={{marginLeft:2}}>T1✓</span>}
              </span>
            );
          })}
        </div>
      </div>

      {/* ---- Junction States ---- */}
      <div className="card">
        <h3>Junction FSM states</h3>
        <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:8, textAlign:'center' }}>
          {junctions.map(jn => {
            const col = MODE_COL[jn.mode];
            return (
              <div key={jn.id} style={{ background:'#0d1626', border:`1px solid ${col}44`, borderRadius:10, padding:'8px 4px' }}>
                <small style={{ display:'block', color:'var(--mute)', fontSize:10.5, textTransform:'uppercase', letterSpacing:'.5px' }}>{jn.id}</small>
                <b style={{ fontFamily:'var(--mono)', fontSize:13, color: col }}>{jn.mode}</b>
                {jn.eta_s != null && (
                  <div style={{ fontSize:10, color:'#8a9bb8', marginTop:2 }}>ETA {jn.eta_s.toFixed(1)}s</div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* ---- ETA Predictions ---- */}
      {etaRows.length > 0 && (
        <div className="card">
          <h3>ETA predictions</h3>
          <table style={{ width:'100%', borderCollapse:'collapse', fontSize:11.5 }}>
            <thead>
              <tr style={{ color:'var(--mute)', textAlign:'left' }}>
                <th style={{ padding:'3px 6px', fontWeight:600 }}>Junction</th>
                <th style={{ padding:'3px 6px', fontWeight:600 }}>Predicted</th>
                <th style={{ padding:'3px 6px', fontWeight:600 }}>Actual</th>
                <th style={{ padding:'3px 6px', fontWeight:600 }}>|Error|</th>
              </tr>
            </thead>
            <tbody>
              {etaRows.map(r => (
                <tr key={r.junction} style={{ borderTop:'1px solid var(--line)' }}>
                  <td style={{ padding:'4px 6px', fontFamily:'var(--mono)', color:'#e6edf7' }}>{r.junction}</td>
                  <td style={{ padding:'4px 6px', fontFamily:'var(--mono)', color:'#38bdf8' }}>{r.predicted}s</td>
                  <td style={{ padding:'4px 6px', fontFamily:'var(--mono)', color:'#22c55e' }}>{r.actual !== '–' ? r.actual+'s' : '–'}</td>
                  <td style={{ padding:'4px 6px', fontFamily:'var(--mono)', color:'#f59e0b' }}>{r.error !== '–' ? r.error+'s' : '–'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ---- A/B Impact ---- */}
      {result && (
        <div className="card">
          <h3>A / B impact</h3>
          <ResponsiveContainer width="100%" height={70}>
            <BarChart data={[
              { name:'Without', val: result.without_s },
              { name:'LifeLane', val: result.with_s },
            ]} layout="vertical" margin={{ top:0, right:8, left:0, bottom:0 }}>
              <XAxis type="number" hide domain={[0, Math.max(result.without_s, result.with_s)*1.1]} />
              <YAxis type="category" dataKey="name" width={60} style={{ fontSize:10, fill:'#8a9bb8' }} />
              <Bar dataKey="val" radius={4}>
                <Cell fill="#8a9bb8" />
                <Cell fill="#22c55e" />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div style={{ display:'flex', gap:8, fontSize:11, color:'#8a9bb8', marginTop:4 }}>
            <span>Saved: <b style={{ color:'#38bdf8', fontFamily:'var(--mono)' }}>{result.saved_s.toFixed(0)}s</b></span>
            {result.without_s > 0 && (
              <span>({Math.round(100*(1-result.with_s/result.without_s))}% faster)</span>
            )}
          </div>
        </div>
      )}

      {/* ---- Model Health ---- */}
      <div className="card">
        <h3>Model health</h3>
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:8, fontSize:12 }}>
          {[
            { label:'Model', val: predictions.model.name },
            { label:'Version', val: predictions.model.version },
            { label:'Latency', val: predictions.model.latency_ms+'ms' },
            { label:'Collisions', val: String(safety.collisions) },
          ].map(({ label, val }) => (
            <div key={label} style={{ background:'#0d1626', border:'1px solid var(--line)', borderRadius:8, padding:'6px 9px' }}>
              <small style={{ display:'block', color:'var(--mute)', fontSize:10, textTransform:'uppercase', letterSpacing:'.5px' }}>{label}</small>
              <span style={{ fontFamily:'var(--mono)', color:'#e6edf7' }}>{val}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
