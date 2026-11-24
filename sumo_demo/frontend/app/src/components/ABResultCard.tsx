// ABResultCard.tsx
import type { Snapshot } from '../types';

interface Props { snapshot: Snapshot; seed: number; }

export default function ABResultCard({ snapshot, seed }: Props) {
  const { result, safety } = snapshot;
  const fmt = (x: number | null | undefined) => x == null ? '–' : x.toFixed(1) + 's';

  const withoutVal = result ? fmt(result.without_s || null) : '–';
  const withVal    = result ? fmt(result.with_s) : '–';
  const savedVal   = result
    ? `${result.saved_s.toFixed(0)}s · ${result.without_s ? Math.round(100*(1-result.with_s/result.without_s)) : 0}%`
    : '–';

  const note = result
    ? `seed ${seed} · 0 collisions both runs: ${safety.collisions === 0 ? '✓' : '✗'}`
    : 'same traffic, same seed';

  return (
    <div className="card">
      <h3>
        A / B result{' '}
        <span style={{ textTransform:'none', letterSpacing:0, color:'var(--mute)', fontSize:11 }}>{note}</span>
      </h3>
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:8, textAlign:'center' }}>
        <div style={{ background:'#0d1626', border:'1px solid var(--line)', borderRadius:10, padding:'8px 4px' }}>
          <small style={{ display:'block', color:'var(--mute)', fontSize:10.5, textTransform:'uppercase', letterSpacing:'.5px' }}>Without</small>
          <b style={{ fontFamily:'var(--mono)', fontSize:19 }}>{withoutVal}</b>
        </div>
        <div style={{ background:'#0d1626', border:'1px solid var(--line)', borderRadius:10, padding:'8px 4px' }}>
          <small style={{ display:'block', color:'var(--mute)', fontSize:10.5, textTransform:'uppercase', letterSpacing:'.5px' }}>LifeLane</small>
          <b style={{ fontFamily:'var(--mono)', fontSize:19, color:'#22c55e' }}>{withVal}</b>
        </div>
        <div style={{ background:'#0d1626', border:'1px solid var(--line)', borderRadius:10, padding:'8px 4px' }}>
          <small style={{ display:'block', color:'var(--mute)', fontSize:10.5, textTransform:'uppercase', letterSpacing:'.5px' }}>Saved</small>
          <b style={{ fontFamily:'var(--mono)', fontSize:19, color:'#38bdf8' }}>{savedVal}</b>
        </div>
      </div>
    </div>
  );
}
