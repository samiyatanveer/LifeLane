/**
 * useSimulation hook – manages Sim lifecycle and exposes a Snapshot at ~60fps.
 * Switch between MockSource and ApiSource via VITE_SOURCE env var.
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { Sim, silentRun } from '../mock/MockSource';
import type { Snapshot, ABResult } from '../types';

const WARM = 30;

export interface SimControls {
  snapshot: Snapshot;
  dispatch: () => void;
  reset: () => void;
  setPreempt: (on: boolean) => void;
  setSpeed: (s: 1 | 2 | 4) => void;
  setMuted: (m: boolean) => void;
}

export function useSimulation(): SimControls & { seed: number; speed: 1|2|4; muted: boolean; preempt: boolean } {
  const seedRef = useRef(11);
  const speedRef = useRef<1|2|4>(1);
  const preemptRef = useRef(true);
  const mutedRef = useRef(false);

  const simRef = useRef<Sim>((() => {
    const s = new Sim(seedRef.current, true);
    while (s.t < WARM) s.step(0.05);
    s.events.length = 0;
    return s;
  })());

  const [snapshot, setSnapshot] = useState<Snapshot>(() => simRef.current.toSnapshot());
  const [seed, setSeed] = useState(seedRef.current);
  const [speed, setSpeedState] = useState<1|2|4>(1);
  const [muted, setMutedState] = useState(false);
  const [preempt, setPreemptState] = useState(true);

  const rafRef = useRef<number>(0);
  const prevRef = useRef(performance.now());
  const accRef = useRef(0);
  const autoTimerRef = useRef(0);

  const resetSim = useCallback((newSeed?: number, newPreempt?: boolean) => {
    const s = newSeed ?? seedRef.current;
    const p = newPreempt ?? preemptRef.current;
    seedRef.current = s;
    const sim = new Sim(s, p, { muted: mutedRef.current });
    while (sim.t < WARM) sim.step(0.05);
    sim.events.length = 0;
    simRef.current = sim;
    accRef.current = 0;
    autoTimerRef.current = 0;
    setSeed(s);
    setSnapshot(sim.toSnapshot());
  }, []);

  useEffect(() => {
    function loop(now: number) {
      const dt = Math.min(0.1, (now - prevRef.current) / 1000);
      prevRef.current = now;
      accRef.current += dt * speedRef.current;
      let n = 0;
      while (accRef.current >= 0.05 && n++ < 40) {
        simRef.current.step(0.05);
        accRef.current -= 0.05;
      }

      const sim = simRef.current;
      const snap = sim.toSnapshot();

      // A/B on completion
      if (snap.result && !sim.__ab) {
        sim.__ab = true;
        const other = silentRun(sim.seed, !sim.preempt, WARM, mutedRef.current);
        const mine = sim.result!.duration;
        const theirs = other.result?.duration ?? null;
        const off = sim.preempt ? theirs : mine;
        const on = sim.preempt ? mine : theirs;
        if (off && on) {
          snap.result = { with_s: on, without_s: off, saved_s: off - on } as ABResult;
        }
      }

      setSnapshot(snap);

      // Autoplay
      const A = sim.amb;
      if (A && A.done && !autoTimerRef.current) autoTimerRef.current = now;
      if (!A && !autoTimerRef.current) autoTimerRef.current = now;
      if (!A && autoTimerRef.current && now - autoTimerRef.current > 3500) {
        sim.dispatch(); autoTimerRef.current = 0;
      }
      if (A?.done && autoTimerRef.current && now - autoTimerRef.current > 9000) {
        seedRef.current++;
        resetSim(seedRef.current, true);
      }

      rafRef.current = requestAnimationFrame(loop);
    }

    rafRef.current = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(rafRef.current);
  }, [resetSim]);

  const dispatch = useCallback(() => { simRef.current.dispatch(); autoTimerRef.current = 0; }, []);
  const reset = useCallback(() => { seedRef.current++; resetSim(); }, [resetSim]);
  const setPreempt = useCallback((on: boolean) => {
    preemptRef.current = on; setPreemptState(on); resetSim(undefined, on);
  }, [resetSim]);
  const setSpeed = useCallback((s: 1|2|4) => { speedRef.current = s; setSpeedState(s); }, []);
  const setMuted = useCallback((m: boolean) => {
    mutedRef.current = m; setMutedState(m); simRef.current.muted = m;
  }, []);

  return { snapshot, dispatch, reset, setPreempt, setSpeed, setMuted, seed, speed, muted, preempt };
}
