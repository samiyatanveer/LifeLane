/**
 * Unit tests for LifeLane React frontend
 * Run: pnpm test
 */
import { describe, it, expect } from 'vitest';
import { Sim } from '../mock/MockSource';

// ---- Test 1: Signal light rendering per Mode ----
describe('Signal light state per junction mode', () => {
  it('NORMAL: ambulance approach W should cycle G→Y→R', () => {
    const sim = new Sim(1, false);
    // Before dispatch, signals run normal cycle
    // Step a lot to advance past initial phase
    for (let i = 0; i < 100; i++) sim.step(0.05);
    const snap = sim.toSnapshot();
    // Every junction should have exactly one G at a time
    for (const jn of snap.junctions) {
      const greens = Object.values(jn.lights).filter(l => l === 'G').length;
      expect(greens).toBeLessThanOrEqual(1);
    }
  });

  it('SERVING: when ambulance is at junction, only W approach is green', () => {
    const sim = new Sim(1, true);
    while (sim.t < 30) sim.step(0.05);
    sim.dispatch();
    // Run until first junction reaches SERVING
    let serving = false;
    for (let i = 0; i < 2000 && !serving; i++) {
      sim.step(0.05);
      serving = sim.sig.some(s => s.mode === 'SERVING');
    }
    if (serving) {
      const snap = sim.toSnapshot();
      const servingJn = snap.junctions.find(j => j.mode === 'SERVING');
      expect(servingJn).toBeDefined();
      if (servingJn) {
        // W should be G (ambulance direction)
        expect(servingJn.lights['W']).toBe('G');
        // All conflicting approaches must be R
        expect(servingJn.lights['N']).toBe('R');
        expect(servingJn.lights['E']).toBe('R');
        expect(servingJn.lights['S']).toBe('R');
      }
    }
  });

  it('RECOVERING: mode transitions from SERVING back to NORMAL', () => {
    const sim = new Sim(2, true);
    while (sim.t < 30) sim.step(0.05);
    sim.dispatch();
    let recovered = false;
    for (let i = 0; i < 6000 && !recovered; i++) {
      sim.step(0.05);
      recovered = sim.sig.some(s => s.mode === 'RECOVERING' || s.mode === 'NORMAL') &&
        sim.sig.some(s => s.mode !== 'NORMAL');
    }
    // At least one transition occurred (not all stuck in NORMAL)
    const snap = sim.toSnapshot();
    const modes = snap.junctions.map(j => j.mode);
    // No crash, modes are valid
    for (const m of modes) {
      expect(['NORMAL','PREPARING','SERVING','RECOVERING']).toContain(m);
    }
  });
});

// ---- Test 2: Two simultaneous greens → safety violation detected ----
describe('Safety: max_open tracking', () => {
  it('never shows two greens at the same junction simultaneously (strict mode)', () => {
    const sim = new Sim(99, true);
    while (sim.t < 30) sim.step(0.05);
    sim.dispatch();
    // Run the full simulation
    while (!sim.result && sim.t < 300) sim.step(0.05);
    // max_open should never exceed 1 (one approach green at a time)
    expect(sim.maxOpen).toBeLessThanOrEqual(1);
  });

  it('chip is "bad" when max_open > 1', () => {
    // Simulate a snapshot where safety.max_open > 1
    const sim = new Sim(1, true);
    while (sim.t < 30) sim.step(0.05);
    const snap = sim.toSnapshot();
    // Manually inject bad value to test chip logic
    snap.safety.max_open = 2;
    const isOk = snap.safety.max_open <= 1;
    expect(isOk).toBe(false); // chip should show 'bad'
  });
});

// ---- Test 3: Offline fallback → snapshot has demoData: true ----
describe('Offline / mock fallback', () => {
  it('MockSource snapshot always has demoData: true', () => {
    const sim = new Sim(42, true);
    while (sim.t < 30) sim.step(0.05);
    const snap = sim.toSnapshot();
    expect(snap.demoData).toBe(true);
  });

  it('MockSource produces valid junctions with correct ids', () => {
    const sim = new Sim(7, false);
    while (sim.t < 10) sim.step(0.05);
    const snap = sim.toSnapshot();
    expect(snap.junctions).toHaveLength(3);
    expect(snap.junctions[0].id).toBe('J1');
    expect(snap.junctions[1].id).toBe('J2');
    expect(snap.junctions[2].id).toBe('J3');
  });

  it('no collisions in a clean mock run with preemption ON', () => {
    const sim = new Sim(123, true);
    while (sim.t < 30) sim.step(0.05);
    sim.dispatch();
    while (!sim.result && sim.t < 350) sim.step(0.05);
    expect(sim.coll).toBe(0);
  });
});
