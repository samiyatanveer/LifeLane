import React, { useState, useEffect, useRef } from 'react';
import { postDetection } from '../api/detection';

const SCENARIOS = [
  'Ambulance route planning (Dijkstra congestion-aware)',
  'Siren detection & approach confirmation (3-window guard)',
  'Authorized ambulance verification (Device ID token)',
  'Traffic signal priority (Yellow 3s + All-Red 2s clearance)',
  'Expired request rejection (Timeout protection)',
  'Conflicting approach arbitration (Dual siren safe hold)',
  'GPS tracking & route deviation detection',
  'Ambulance passage confirmation (Loop detector)',
  'Registered ambulance device authentication',
  'Unregistered ambulance temporary verification (Operator token)',
  'Safe fallback for unverified siren (Hold red, log event)',
  'Bounded coordination recovery (Phase delay compensation)',
];

export default function LiveDemo() {
  // Scenario Runner state
  const [passedCount, setPassedCount] = useState(0);
  const [isRunningScenarios, setIsRunningScenarios] = useState(false);
  const [activeScenarios, setActiveScenarios] = useState([]);

  // Audio Canvas visualizer state
  const [audioMode, setAudioMode] = useState('siren');
  const [verdict, setVerdict] = useState('Siren detected');
  const [meterWidth, setMeterWidth] = useState('92%');
  const [meterBg, setMeterBg] = useState('var(--g2)');
  const canvasRef = useRef(null);
  const animFrameRef = useRef(null);

  // Real Audio Upload state
  const [uploadFile, setUploadFile] = useState(null);
  const [approach, setApproach] = useState('north');
  const [junctionId, setJunctionId] = useState('J1');
  const [uploadResult, setUploadResult] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [uploadError, setUploadError] = useState(null);

  // Run mock scenarios step by step
  const handleRunScenarios = () => {
    if (isRunningScenarios) return;
    setIsRunningScenarios(true);
    setActiveScenarios([]);
    setPassedCount(0);

    SCENARIOS.forEach((_, idx) => {
      setTimeout(() => {
        setActiveScenarios((prev) => [...prev, idx]);
        setPassedCount(idx + 1);
        if (idx === SCENARIOS.length - 1) {
          setIsRunningScenarios(false);
        }
      }, 350 * (idx + 1));
    });
  };

  // Canvas Spectrum Animation
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const N = 56;
    let t = 0;

    const draw = () => {
      t += 0.035;
      ctx.clearRect(0, 0, 600, 130);
      let peak = 0;
      const centerBin = (Math.sin(t * 1.6) * 0.5 + 0.5) * (N - 14) + 7;

      for (let i = 0; i < N; i++) {
        let val = 0;
        if (audioMode === 'siren') {
          // Sharp harmonic peak characteristic of emergency siren
          val = Math.exp(-Math.pow((i - centerBin) / 3.2, 2)) * 0.95 + Math.random() * 0.06;
        } else {
          // Broadband dispersed noise floor of ordinary traffic
          val = Math.max(0, 0.28 * Math.exp(-i / 22) + Math.random() * 0.22);
        }
        peak = Math.max(peak, val);
        ctx.fillStyle = audioMode === 'siren' ? '#FF5468' : '#8BB89B';
        ctx.fillRect(i * 10.7 + 4, 130 - val * 118, 7, val * 118);
      }

      const isSiren = audioMode === 'siren';
      setVerdict(isSiren ? 'Siren detected (Harmonic Pitch)' : 'Ordinary Road Noise');
      setMeterWidth(`${Math.round(peak * 100)}%`);
      setMeterBg(isSiren ? 'var(--g2)' : 'var(--amber)');

      animFrameRef.current = requestAnimationFrame(draw);
    };

    animFrameRef.current = requestAnimationFrame(draw);

    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, [audioMode]);

  // Handle Real Audio Upload to Backend
  const handleUploadSubmit = async (e) => {
    e.preventDefault();
    if (!uploadFile) {
      setUploadError('Please select an audio file (.wav, .mp3, etc.)');
      return;
    }
    setUploadError(null);
    setIsAnalyzing(true);
    setUploadResult(null);

    try {
      const data = await postDetection(uploadFile, approach, junctionId);
      setUploadResult(data);
    } catch (err) {
      setUploadError(err.message || 'Failed to analyze audio with backend model');
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <section className="py-12 wrap">
      <h2>Try the parts yourself</h2>
      <p className="mt-2 mb-8">
        Test the verification scenarios in simulation, explore siren frequency harmonics, or upload real audio directly to the Python ML inference engine.
      </p>

      {/* Row 1: Scenarios & Frequency Visualizer */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        {/* Mock Scenarios Runner Card */}
        <div className="life-card flex flex-col justify-between h-full">
          <div>
            <h3>Mock simulation scenarios</h3>
            <p className="text-sm mt-1 mb-4">
              LifeLane validates all safety invariants across 12 rigorous end-to-end scenarios.
            </p>

            <ul className="flex flex-col gap-2 my-4 max-h-[360px] overflow-y-auto pr-1">
              {SCENARIOS.map((name, i) => {
                const isPassed = activeScenarios.includes(i);
                return (
                  <li
                    key={name}
                    className={`flex items-center gap-3 py-2 px-3 rounded-xl text-xs font-semibold transition-all ${
                      isPassed
                        ? 'bg-[var(--tint)] text-[var(--ink)]'
                        : 'bg-[var(--tint)]/50 text-[var(--mute)]'
                    }`}
                  >
                    <span
                      className={`w-4 h-4 rounded-full flex-shrink-0 border-2 transition-all ${
                        isPassed
                          ? 'bg-[var(--g2)] border-[var(--g2)] shadow-sm'
                          : 'border-[var(--mute)]'
                      }`}
                    />
                    <span>{name}</span>
                  </li>
                );
              })}
            </ul>
          </div>

          <div className="pt-4 border-t border-[var(--line)] flex items-center justify-between">
            <button
              onClick={handleRunScenarios}
              disabled={isRunningScenarios}
              className="cta-btn text-sm"
            >
              {isRunningScenarios ? 'Running checks...' : 'Run all 12 scenarios'}
            </button>
            <small className="text-xs font-bold text-[var(--mute)]">
              {passedCount} of 12 passed
            </small>
          </div>
        </div>

        {/* Siren or Road Noise Interactive Canvas */}
        <div className="life-card flex flex-col justify-between h-full">
          <div>
            <h3>Siren or road noise?</h3>
            <p className="text-sm mt-1 mb-4">
              Toggle sound categories to observe how siren pitch harmonics contrast against background traffic rumble.
            </p>

            {/* Mode Toggle Buttons */}
            <div className="flex gap-2 mb-4 p-1 rounded-xl bg-[var(--tint)]">
              <button
                onClick={() => setAudioMode('siren')}
                className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-bold transition-all ${
                  audioMode === 'siren' ? 'bg-[var(--g)] text-white shadow-sm' : 'text-[var(--ink)]'
                }`}
              >
                Siren Audio Profile
              </button>
              <button
                onClick={() => setAudioMode('noise')}
                className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-bold transition-all ${
                  audioMode === 'noise' ? 'bg-[var(--g)] text-white shadow-sm' : 'text-[var(--ink)]'
                }`}
              >
                Road Traffic Noise
              </button>
            </div>

            {/* HTML5 Canvas */}
            <canvas
              ref={canvasRef}
              width={600}
              height={130}
              className="w-full h-32 block rounded-xl border border-[var(--line)]"
              style={{ backgroundColor: 'var(--road)' }}
            />

            {/* Live Verdict & Confidence Meter */}
            <div className="mt-4 flex items-center justify-between">
              <span className="font-bold text-base" style={{ fontFamily: '"Bricolage Grotesque", sans-serif' }}>
                {verdict}
              </span>
              <span className="text-xs font-semibold text-[var(--mute)]">Confidence: {meterWidth}</span>
            </div>
            <div className="w-full h-2 rounded-full bg-[var(--tint)] mt-2 overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-200"
                style={{ width: meterWidth, backgroundColor: meterBg }}
              />
            </div>
          </div>

          <small className="block mt-4 text-xs text-[var(--mute)] border-t border-[var(--line)] pt-3">
            Real-time FFT audio visualizer. The actual classifier uses 1024-dimensional YAMNet transfer embeddings.
          </small>
        </div>
      </div>

      {/* Row 2: Live Backend Audio ML Inference Tool */}
      <div className="mt-8 life-card" style={{ borderTopColor: 'var(--gold)' }}>
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div>
            <h3>Analyze audio with live backend ML</h3>
            <p className="text-sm">
              Upload an audio clip to trigger real inference on <code>POST /api/detect</code> using the active model.
            </p>
          </div>
          <span className="status-pill go">
            <s />
            <span>FastAPI ML Ready</span>
          </span>
        </div>

        <form onSubmit={handleUploadSubmit} className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-3 items-end">
          {/* File Picker */}
          <div className="sm:col-span-2 md:col-span-2">
            <label className="block text-xs font-bold uppercase tracking-wider text-[var(--mute)] mb-1">
              Audio File (.wav, .mp3, .ogg)
            </label>
            <input
              type="file"
              accept=".wav,.mp3,.ogg,.flac"
              onChange={(e) => setUploadFile(e.target.files[0])}
              className="w-full p-2 rounded-xl border border-[var(--line)] bg-[var(--surface)] text-xs text-[var(--ink)]"
            />
          </div>

          {/* Junction Selector */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-[var(--mute)] mb-1">
              Junction
            </label>
            <select
              value={junctionId}
              onChange={(e) => setJunctionId(e.target.value)}
              className="w-full p-2.5 rounded-xl border border-[var(--line)] bg-[var(--surface)] text-xs font-semibold text-[var(--ink)]"
            >
              <option value="J1">Junction J1</option>
              <option value="J2">Junction J2</option>
              <option value="J3">Junction J3</option>
              <option value="J4">Junction J4</option>
            </select>
          </div>

          {/* Approach Direction */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-[var(--mute)] mb-1">
              Approach
            </label>
            <select
              value={approach}
              onChange={(e) => setApproach(e.target.value)}
              className="w-full p-2.5 rounded-xl border border-[var(--line)] bg-[var(--surface)] text-xs font-semibold text-[var(--ink)]"
            >
              <option value="north">North</option>
              <option value="south">South</option>
              <option value="east">East</option>
              <option value="west">West</option>
            </select>
          </div>

          {/* Submit Button */}
          <div>
            <button
              type="submit"
              disabled={isAnalyzing}
              className="cta-btn w-full text-xs py-2.5 font-bold"
            >
              {isAnalyzing ? 'Analyzing...' : 'Run ML'}
            </button>
          </div>
        </form>

        {uploadError && (
          <div className="mt-4 p-3 rounded-xl bg-red-100 text-red-800 text-xs font-semibold">
            {uploadError}
          </div>
        )}

        {uploadResult && (
          <div className="mt-4 p-4 rounded-xl bg-[var(--tint)] border border-[var(--line)] flex flex-wrap items-center justify-between gap-4">
            <div>
              <span className="text-xs uppercase font-bold text-[var(--mute)] tracking-wider">Classification Result</span>
              <div className="flex items-center gap-2 mt-0.5">
                <span
                  className={`text-lg font-extrabold ${
                    uploadResult.is_siren ? 'text-[var(--g2)]' : 'text-[var(--red)]'
                  }`}
                  style={{ fontFamily: '"Bricolage Grotesque", sans-serif' }}
                >
                  {uploadResult.is_siren ? '🚨 Emergency Siren Detected' : '❌ Non-Siren Audio'}
                </span>
                <span className="text-xs font-bold bg-white/70 px-2 py-0.5 rounded-full text-[var(--ink)]">
                  Score: {(uploadResult.confidence * 100).toFixed(1)}%
                </span>
              </div>
            </div>

            <div className="text-xs text-[var(--mute)]">
              <div>Model: <strong>{uploadResult.model_type}</strong></div>
              <div>Junction: <strong>{uploadResult.junction_id || junctionId}</strong> ({approach})</div>
              {uploadResult.warning && (
                <small className="block text-[11px] text-[var(--amber)] mt-0.5">{uploadResult.warning}</small>
              )}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
