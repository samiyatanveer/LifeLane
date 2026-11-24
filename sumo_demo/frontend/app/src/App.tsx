// App.tsx – assembles all components, matches lifelane_demo.html layout exactly
import { useState, useRef, useEffect } from 'react';
import { useSimulation } from './hooks/useSimulation';
import { type Camera } from './renderer';
import Header from './components/Header';
import MapCanvas from './components/MapCanvas';
import ControlsCard from './components/ControlsCard';
import CorridorTrack from './components/CorridorTrack';
import JunctionCard from './components/JunctionCard';
import SafetyMonitor from './components/SafetyMonitor';
import ABResultCard from './components/ABResultCard';
import EventLog from './components/EventLog';
import ModelPanel from './components/ModelPanel';
import type { Snapshot } from './types';

const HISTORY_MAX = 120;

export default function App() {
  const sim = useSimulation();
  const { snapshot, dispatch, reset, setPreempt, setSpeed, setMuted } = sim;

  // Local UI state
  const [follow, setFollow] = useState(true);
  const [autoplay, setAutoplay] = useState(true);
  const [showModel, setShowModel] = useState(false);
  const [banner, setBanner] = useState<{ msg: string; col: string } | null>(null);
  const bannerTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Camera ref for renderer
  const camRef = useRef<Camera>({ x: 320, y: 0, z: 1, follow });

  // History buffer for ModelPanel charts
  const historyRef = useRef<Snapshot[]>([]);
  useEffect(() => {
    historyRef.current.push(snapshot);
    if (historyRef.current.length > HISTORY_MAX) historyRef.current.shift();
  }, [snapshot]);

  // Banner when ambulance arrives
  const prevDone = useRef(false);
  useEffect(() => {
    const done = snapshot.ambulance?.done;
    if (done && !prevDone.current && snapshot.result) {
      const r = snapshot.result;
      const msg = `Arrived in ${r.with_s.toFixed(1)} s` +
        (r.without_s ? ` · LifeLane saves ${r.saved_s.toFixed(0)} s` : '');
      setBanner({ msg, col: '#22c55e' });
      if (bannerTimer.current) clearTimeout(bannerTimer.current);
      bannerTimer.current = setTimeout(() => setBanner(null), 4500);
    }
    prevDone.current = !!done;
  }, [snapshot.ambulance?.done, snapshot.result]);

  // t0 for event log timestamps
  const t0 = snapshot.ambulance ? snapshot.t - snapshot.ambulance.elapsed : 0;

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100vh', overflow:'hidden' }}>
      <Header snapshot={snapshot} />

      <main className="main-layout" style={{ flex:1, minHeight:0, display:'flex', gap:0 }}>
        {/* ---- Left: Canvas stage ---- */}
        <section className="stage-section" style={{ position:'relative', flex:1, minWidth:0, background:'#0a101c' }}>
          <MapCanvas snapshot={snapshot} cam={camRef.current} follow={follow} />

          {/* Overlay title */}
          <div style={{ position:'absolute', left:14, top:12, pointerEvents:'none' }}>
            <h1 style={{ margin:0, fontSize:15, letterSpacing:'.3px' }}>Hospital Avenue</h1>
            <p style={{ margin:'2px 0 0', color:'var(--mute)', fontSize:12 }}>
              3 signalised junctions · one approach open at a time · all others stop at red
            </p>
          </div>

          {/* Banner */}
          {banner && (
            <div style={{
              position:'absolute', left:'50%', top:14, transform:'translateX(-50%)',
              padding:'8px 16px', borderRadius:12, background:'rgba(16,26,43,.94)',
              border:`1px solid ${banner.col}`, fontWeight:600, fontSize:13,
              color: banner.col, whiteSpace:'nowrap', pointerEvents:'none',
              animation:'fadeIn 0.25s ease',
            }}>
              {banner.msg}
            </div>
          )}

          {/* Legend */}
          <div style={{ position:'absolute', left:14, bottom:12, display:'flex', gap:8, flexWrap:'wrap', pointerEvents:'none' }}>
            {[
              { col:'#22c55e', label:'GREEN – only one approach' },
              { col:'#f59e0b', label:'YELLOW – finish crossing' },
              { col:'#ef4444', label:'RED – stop at line' },
              { col:'#fff', shadow:'0 0 6px #ef4444', label:'Ambulance' },
            ].map(({ col, shadow, label }) => (
              <span key={label} style={{
                display:'flex', alignItems:'center', gap:6,
                background:'rgba(16,26,43,.88)', border:'1px solid var(--line)',
                padding:'4px 9px', borderRadius:999, fontSize:11.5, color:'#c9d6ec',
              }}>
                <i style={{ width:10, height:10, borderRadius:'50%', background:col, boxShadow:shadow, display:'inline-block' }} />
                {label}
              </span>
            ))}
          </div>

          {/* Model Panel toggle */}
          <button
            onClick={() => setShowModel(v => !v)}
            style={{
              position:'absolute', right:12, bottom:12, fontSize:11, padding:'5px 10px',
              borderRadius:8, background:'rgba(16,26,43,.88)', border:'1px solid var(--line)',
              color:'var(--mute)',
            }}
          >
            {showModel ? '▼ Hide' : '▲ Model'} Panel
          </button>
        </section>

        {/* ---- Right: Aside panel ---- */}
        <aside className="aside-panel" style={{
          width:384, maxWidth:'44vw', borderLeft:'1px solid var(--line)',
          background:'var(--panel2)', overflowY:'auto', padding:12,
          display:'flex', flexDirection:'column', gap:10,
        }}>
          <ControlsCard
            preempt={sim.preempt}
            speed={sim.speed}
            follow={follow}
            autoplay={autoplay}
            muted={sim.muted}
            ambActive={!!snapshot.ambulance && !snapshot.ambulance.done}
            onDispatch={dispatch}
            onReset={reset}
            onPreempt={setPreempt}
            onSpeed={(s) => setSpeed(s as 1|2|4)}
            onFollow={setFollow}
            onAutoplay={setAutoplay}
            onMuted={setMuted}
          />

          <CorridorTrack snapshot={snapshot} />

          <JunctionCard junctions={snapshot.junctions} />

          <SafetyMonitor snapshot={snapshot} />

          <ABResultCard snapshot={snapshot} seed={sim.seed} />

          <EventLog events={snapshot.events} t0={t0} />

          {showModel && (
            <ModelPanel snapshot={snapshot} history={historyRef.current} />
          )}

          <p style={{ color:'var(--mute)', fontSize:12, margin:0 }}>
            Mock physics runs in your browser. Same logic maps 1-to-1 onto SUMO + TraCI.
          </p>
        </aside>
      </main>

      <style>{`@keyframes fadeIn{from{opacity:0}to{opacity:1}}`}</style>
    </div>
  );
}
