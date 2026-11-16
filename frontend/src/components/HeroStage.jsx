import React, { useState, useRef, useEffect, useCallback } from 'react';

export default function HeroStage({ onNavigateToRoute, onNavigateToSystem }) {
  const [running, setRunning] = useState(false);
  const [hudState, setHudState] = useState({ class: '', text: 'Waiting for a request' });
  const [eta, setEta] = useState('--');
  const [buttonText, setButtonText] = useState('Dispatch ambulance');
  const [ambX, setAmbX] = useState(-90);
  const [signals, setSignals] = useState(['normal', 'normal', 'normal']);

  const animRef = useRef(null);
  const t0Ref = useRef(null);
  const xs = [190, 410, 630];
  const X0 = -90;
  const X1 = 850;
  const DUR = 8500;

  const step = useCallback((ts) => {
    if (!t0Ref.current) t0Ref.current = ts;
    const progress = Math.min((ts - t0Ref.current) / DUR, 1);
    const x = X0 + (X1 - X0) * progress;
    setAmbX(x);

    let activeSignal = -1;
    let isRecovering = false;

    const nextSignals = xs.map((sx, i) => {
      const d = sx - (x + 76);
      if (d > -10 && d < 230) {
        activeSignal = i;
        return 'go';
      } else if (d <= -10 && d > -150) {
        isRecovering = true;
        return 'rec';
      }
      return 'normal';
    });
    setSignals(nextSignals);

    if (progress < 0.08) {
      setHudState({ class: 'alert', text: 'Siren confirmed, request verified' });
    } else if (activeSignal >= 0) {
      setHudState({ class: 'go', text: `Priority granted at Signal J${activeSignal + 1}` });
    } else if (isRecovering) {
      setHudState({ class: 'rec', text: 'Ambulance passed, signal recovering' });
    } else if (progress < 1) {
      setHudState({ class: 'go', text: 'Corridor clear ahead to hospital' });
    }

    const remainingSecs = Math.max(0, Math.ceil((DUR * (1 - progress)) / 1000));
    setEta(`${remainingSecs} s`);

    if (progress < 1) {
      animRef.current = requestAnimationFrame(step);
    } else {
      setRunning(false);
      setHudState({ class: '', text: 'Normal traffic cycle restored' });
      setEta('Arrived at JPMC');
      setButtonText('Dispatch again');
    }
  }, []);

  const handleStart = () => {
    if (running) return;
    setRunning(true);
    t0Ref.current = null;
    animRef.current = requestAnimationFrame(step);
  };

  useEffect(() => {
    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, []);

  return (
    <div className="relative overflow-hidden pt-10 pb-16" style={{ background: 'linear-gradient(180deg, var(--tint), var(--bg))' }}>
      {/* Decorative Pakistani Crescent & Star Watermark */}
      <svg
        className="absolute -right-12 -top-8 w-80 md:w-96 opacity-10 pointer-events-none select-none text-[var(--g)]"
        viewBox="0 0 60 60"
        aria-hidden="true"
      >
        <path d="M33 4a26 26 0 1 0 0 52a20.5 20.5 0 1 1 0-52z" fill="currentColor" />
        <polygon points="45,20 47.8,28 56,28 49.4,33 52,41 45,36 38,41 40.6,33 34,28 42.2,28" fill="currentColor" />
      </svg>

      <div className="wrap">
        <h1 className="max-w-[17ch]">
          A cleared road for every ambulance in Pakistan.
        </h1>
        <p className="mt-4 mb-6 text-lg max-w-[62ch]">
          LifeLane listens for sirens, checks that the ambulance is authorized, and turns each signal on its route green just in time. Once the ambulance has passed, traffic goes back to normal.
        </p>

        {/* Action Buttons */}
        <div className="flex flex-wrap gap-3">
          <button
            onClick={handleStart}
            disabled={running}
            className="cta-btn"
          >
            {buttonText}
          </button>
          <button
            onClick={onNavigateToRoute}
            className="cta-btn alt"
          >
            Plan a hospital route
          </button>
          <button
            onClick={onNavigateToSystem}
            className="cta-btn alt"
          >
            See how it works
          </button>
        </div>

        {/* Stage: Interactive Animated Road Simulation */}
        <div
          className="mt-10 p-4 sm:p-5 rounded-3xl border border-[var(--line)] bg-[var(--surface)] shadow-2xl"
          style={{ boxShadow: '0 24px 50px -32px rgba(1,65,28,.45)' }}
        >
          <svg
            viewBox="0 0 800 230"
            role="img"
            aria-label="Animated road with an ambulance passing three traffic signals"
            className="w-full h-auto block rounded-2xl"
          >
            {/* Asphalt Road */}
            <rect x="0" y="120" width="800" height="70" rx="10" fill="var(--road)" />
            {/* Dashed Center Dividing Line */}
            <line
              x1="0"
              y1="155"
              x2="800"
              y2="155"
              stroke="#ffffff"
              strokeOpacity="0.55"
              strokeWidth="3"
              strokeDasharray="22 16"
            />

            {/* Traffic Signal 1 (J1) */}
            <g className={`sig ${signals[0]}`} transform="translate(190 0)">
              <rect x="-3" y="60" width="6" height="60" fill="var(--mute)" />
              <rect x="-14" y="38" width="28" height="28" rx="6" fill="#1b241e" />
              <circle className="lamp" cx="0" cy="52" r="11" />
              <text x="0" y="30" textAnchor="middle" fontSize="11" fontWeight="700" fill="var(--mute)">J1</text>
            </g>

            {/* Traffic Signal 2 (J2) */}
            <g className={`sig ${signals[1]}`} transform="translate(410 0)">
              <rect x="-3" y="60" width="6" height="60" fill="var(--mute)" />
              <rect x="-14" y="38" width="28" height="28" rx="6" fill="#1b241e" />
              <circle className="lamp" cx="0" cy="52" r="11" />
              <text x="0" y="30" textAnchor="middle" fontSize="11" fontWeight="700" fill="var(--mute)">J2</text>
            </g>

            {/* Traffic Signal 3 (J3) */}
            <g className={`sig ${signals[2]}`} transform="translate(630 0)">
              <rect x="-3" y="60" width="6" height="60" fill="var(--mute)" />
              <rect x="-14" y="38" width="28" height="28" rx="6" fill="#1b241e" />
              <circle className="lamp" cx="0" cy="52" r="11" />
              <text x="0" y="30" textAnchor="middle" fontSize="11" fontWeight="700" fill="var(--mute)">J3</text>
            </g>

            {/* Animated Ambulance Vehicle */}
            <g transform={`translate(${ambX} 128)`}>
              {/* White Vehicle Chassis */}
              <rect width="76" height="34" rx="8" fill="#ffffff" stroke="#e0e0e0" strokeWidth="1" />
              {/* Emergency Tint Windows */}
              <rect x="50" y="6" width="20" height="14" rx="3" fill="#9CC8F5" />
              {/* Red Crescent / Cross Emblem */}
              <rect x="21" y="5" width="6" height="20" fill="#D62839" />
              <rect x="12" y="12" width="22" height="6" fill="#D62839" />
              {/* Flashing Roof Siren Light */}
              <circle className="siren" cx="38" cy="-4" r="5" fill="#D62839" />
              {/* Wheels */}
              <circle cx="18" cy="35" r="7" fill="#222222" />
              <circle cx="18" cy="35" r="3" fill="#888888" />
              <circle cx="58" cy="35" r="7" fill="#222222" />
              <circle cx="58" cy="35" r="3" fill="#888888" />
            </g>
          </svg>

          {/* Legend */}
          <div className="flex flex-wrap gap-4 sm:gap-6 pt-3 pb-1 text-sm font-medium border-t border-[var(--line)] mt-3">
            <span className="inline-flex items-center gap-2">
              <i className="w-3.5 h-3.5 rounded-full inline-block" style={{ backgroundColor: 'var(--red)' }} />
              Red: Normal fixed-time cycle
            </span>
            <span className="inline-flex items-center gap-2">
              <i className="w-3.5 h-3.5 rounded-full inline-block bg-[#22B866]" />
              Green: Priority wave for ambulance
            </span>
            <span className="inline-flex items-center gap-2">
              <i className="w-3.5 h-3.5 rounded-full inline-block" style={{ backgroundColor: 'var(--amber)' }} />
              Amber: Safe clearing & recovery
            </span>
          </div>

          {/* Live HUD Status Row */}
          <div className="flex flex-wrap items-center justify-between gap-3 pt-3">
            <span className={`status-pill ${hudState.class}`}>
              <s />
              <span>{hudState.text}</span>
            </span>
            <div className="text-sm font-medium">
              Time to destination:{' '}
              <b className="text-base" style={{ fontFamily: '"Bricolage Grotesque", sans-serif', color: 'var(--g2)' }}>
                {eta}
              </b>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
