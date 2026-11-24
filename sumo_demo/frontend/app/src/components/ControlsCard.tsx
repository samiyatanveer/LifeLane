// ControlsCard.tsx
interface Props {
  preempt: boolean;
  speed: 1 | 2 | 4;
  follow: boolean;
  autoplay: boolean;
  muted: boolean;
  ambActive: boolean;
  onDispatch: () => void;
  onReset: () => void;
  onPreempt: (on: boolean) => void;
  onSpeed: (s: 1 | 2 | 4) => void;  onFollow: (f: boolean) => void;
  onAutoplay: (a: boolean) => void;
  onMuted: (m: boolean) => void;
}

export default function ControlsCard({ preempt, speed, follow, autoplay, muted, ambActive,
  onDispatch, onReset, onPreempt, onSpeed, onFollow, onAutoplay, onMuted }: Props) {

  return (
    <div className="card">
      <h3>Controls</h3>
      <div style={{ display:'flex', gap:8, flexWrap:'wrap', marginBottom:9 }}>
        <button className="primary" disabled={ambActive} onClick={onDispatch}>▶ Dispatch ambulance</button>
        <button onClick={onReset}>↺ Reset</button>
      </div>
      <div style={{ display:'flex', gap:8, flexWrap:'wrap', marginBottom:9 }}>
        {/* LifeLane ON/OFF */}
        <div className="seg">
          <button className={preempt ? 'on' : ''} onClick={() => onPreempt(true)}>LifeLane ON</button>
          <button className={!preempt ? 'on' : ''} onClick={() => onPreempt(false)}>OFF</button>
        </div>
        {/* Speed */}
        <div className="seg">
          {([1,2,4] as const).map(s => (
            <button key={s} className={speed === s ? 'on' : ''} onClick={() => onSpeed(s)}>{s}×</button>
          ))}
        </div>
        {/* Camera */}
        <div className="seg">
          <button className={!follow ? 'on' : ''} onClick={() => onFollow(false)}>Overview</button>
          <button className={follow ? 'on' : ''} onClick={() => onFollow(true)}>Follow</button>
        </div>
      </div>
      <div style={{ display:'flex', gap:14, flexWrap:'wrap' }}>
        <label style={{ display:'flex', gap:7, alignItems:'center', fontSize:12.5, color:'#c9d6ec', cursor:'pointer', userSelect:'none' }}>
          <input type="checkbox" checked={autoplay} onChange={e => onAutoplay(e.target.checked)} />
          Autoplay loop
        </label>
        <label style={{ display:'flex', gap:7, alignItems:'center', fontSize:12.5, color:'#c9d6ec', cursor:'pointer', userSelect:'none' }}>
          <input type="checkbox" checked={muted} onChange={e => onMuted(e.target.checked)} />
          Mute siren (fail-safe test)
        </label>
      </div>
    </div>
  );
}
