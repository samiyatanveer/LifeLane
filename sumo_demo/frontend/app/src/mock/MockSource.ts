/**
 * MockSource – ports the entire Sim + Sig logic from lifelane_demo.html to TypeScript.
 * Produces Snapshot objects at any step rate.
 */
import type { Snapshot, Vehicle, Junction, MockVehicle, MockLane, Approach, Light, Mode } from '../types';

// ---- CONFIG & GEOMETRY (must match lifelane_demo.html exactly) ----
export const X = [130, 300, 470] as const;
export const END = 640, ER_X = 590;
export const HALF = 8.75, BOX = 7, STOPOFF = 12, SIDE = 130;
const GREEN_T = 9, YEL = 3, ALLRED = 2;
const MIC = 190, PTH = 0.70, LEAD = 10, MAXSERVE = 45;
const MINGAP = 3, TAU = 0.5, B = 4.5, BMAX = 8;
export const APPR: Approach[] = ['W', 'N', 'E', 'S'];
export const WORLD = { x0: -25, y0: -150, x1: 665, y1: 150 };
export const MODE_COL: Record<Mode, string> = {
  NORMAL: '#8a9bb8', PREPARING: '#f59e0b', SERVING: '#22c55e', RECOVERING: '#38bdf8',
};
export const SIG_COL: Record<string, string> = { R: '#ef4444', Y: '#f59e0b', G: '#22c55e' };

const CAR_COLS = ['#7dd3fc','#a78bfa','#fcd34d','#f9a8d4','#86efac','#fdba74','#cbd5e1','#fca5a5','#67e8f9','#c4b5fd'];

function mulberry(a: number): () => number {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function makeLanes(seed: number): MockLane[] {
  const L: MockLane[] = [];
  let k = 1;
  L.push({ k: k++, id: 'E_A', ap: 'W', len: END, hd: 0, rate: 0.16, pt: s => [s, 7],
    stops: X.map((x, j) => ({ j, s: x - STOPOFF })), veh: [], r: mulberry(seed * 131 + 1) });
  L.push({ k: k++, id: 'E_B', ap: 'W', len: END, hd: 0, rate: 0, amb: true, pt: s => [s, 3.5],
    stops: X.map((x, j) => ({ j, s: x - STOPOFF })), veh: [], r: mulberry(seed * 131 + 2) });
  L.push({ k: k++, id: 'W_A', ap: 'E', len: END, hd: Math.PI, rate: 0.14, pt: s => [END - s, -7],
    stops: X.map((x, j) => ({ j, s: END - (x + STOPOFF) })), veh: [], r: mulberry(seed * 131 + 3) });
  X.forEach((x, j) => {
    L.push({ k: k++, id: 'N' + j, ap: 'N', len: 2 * SIDE, hd: Math.PI / 2, rate: 0.055,
      pt: s => [x - 3.5, -SIDE + s], stops: [{ j, s: SIDE - STOPOFF }], veh: [], r: mulberry(seed * 131 + k) });
    k++;
    L.push({ k: k++, id: 'S' + j, ap: 'S', len: 2 * SIDE, hd: -Math.PI / 2, rate: 0.055,
      pt: s => [x + 3.5, SIDE - s], stops: [{ j, s: SIDE - STOPOFF }], veh: [], r: mulberry(seed * 131 + k) });
    k++;
  });
  return L;
}

// ---- SIGNAL CONTROLLER ----
class Sig {
  j: number; mode: Mode; i: number; phase: string; t: number; target: number; hold: number;
  constructor(j: number, r: () => number) {
    this.j = j; this.mode = 'NORMAL'; this.i = Math.floor(r() * 4); this.phase = 'G';
    this.t = r() * GREEN_T * 0.8; this.target = 0; this.hold = 0;
  }
  state(ap: Approach): Light {
    if (APPR[this.i] !== ap) return 'R';
    return this.phase === 'G' ? 'G' : this.phase === 'Y' ? 'Y' : 'R';
  }
  begin(ap: Approach) {
    this.mode = 'PREPARING'; this.target = APPR.indexOf(ap);
    if (this.phase === 'G') {
      if (this.i === this.target) { this.mode = 'SERVING'; this.hold = 0; }
      else { this.phase = 'Y'; this.t = 0; }
    }
  }
  release() { this.mode = 'RECOVERING'; this.phase = 'Y'; this.t = 0; }
  step(dt: number) {
    this.t += dt;
    if (this.mode === 'SERVING') { this.hold += dt; return; }
    if (this.phase === 'G') {
      if (this.mode === 'NORMAL' && this.t >= GREEN_T) { this.phase = 'Y'; this.t = 0; }
    } else if (this.phase === 'Y') {
      if (this.t >= YEL) { this.phase = 'AR'; this.t = 0; }
    } else if (this.t >= ALLRED) {
      if (this.mode === 'PREPARING') { this.i = this.target; this.phase = 'G'; this.t = 0; this.mode = 'SERVING'; this.hold = 0; }
      else if (this.mode === 'RECOVERING') { this.i = (this.target + 1) % 4; this.phase = 'G'; this.t = 0; this.mode = 'NORMAL'; }
      else { this.i = (this.i + 1) % 4; this.phase = 'G'; this.t = 0; }
    }
  }
}

function rectOf(v: MockVehicle, lane: MockLane) {
  const [cx, cy] = lane.pt(v.s - v.len / 2);
  return { cx, cy, c: Math.cos(lane.hd), s: Math.sin(lane.hd), L: v.len / 2, W: v.w / 2 };
}

function overlap(a: ReturnType<typeof rectOf>, b: ReturnType<typeof rectOf>): number {
  const axes: [number, number][] = [[a.c, a.s], [-a.s, a.c], [b.c, b.s], [-b.s, b.c]];
  let minPen = 1e9;
  for (const [ax, ay] of axes) {
    const ra = a.L * Math.abs(a.c * ax + a.s * ay) + a.W * Math.abs(-a.s * ax + a.c * ay);
    const rb = b.L * Math.abs(b.c * ax + b.s * ay) + b.W * Math.abs(-b.s * ax + b.c * ay);
    const d = Math.abs((b.cx - a.cx) * ax + (b.cy - a.cy) * ay);
    minPen = Math.min(minPen, ra + rb - d);
    if (d > ra + rb) return -1;
  }
  return minPen;
}

// ---- SIM CLASS ----
export class Sim {
  seed: number; preempt: boolean; muted: boolean;
  t: number; rn: () => number;
  lanes: MockLane[]; sig: Sig[];
  trk: { c: number; p: number; t1: boolean; t2: boolean; t3: boolean; eta: number }[];
  amb: MockVehicle | null; vid: number; frameT: number;
  events: { t: number; msg: string; cls: string }[];
  coll: number; pairs: Set<string>; maxOpen: number; held: number; minClear: number;
  ambStopped: number; result: { duration: number; stopped: number } | null; t0: number;
  _fs: Record<number, number>;
  __logged: number; __ab: boolean;

  constructor(seed: number, preempt: boolean, opts: { muted?: boolean } = {}) {
    this.seed = seed; this.preempt = preempt; this.muted = !!opts.muted;
    this.t = 0; this.rn = mulberry(seed * 7 + 1);
    this.lanes = makeLanes(seed);
    this.sig = X.map((_, j) => new Sig(j, mulberry(seed * 17 + j)));
    this.trk = X.map(() => ({ c: 0, p: 0, t1: false, t2: false, t3: false, eta: 99 }));
    this.amb = null; this.vid = 1; this.frameT = 0; this.events = [];
    this.coll = 0; this.pairs = new Set(); this.maxOpen = 1; this.held = 0; this.minClear = 99;
    this.ambStopped = 0; this.result = null; this.t0 = 0;
    this._fs = {}; this.__logged = 0; this.__ab = false;
  }

  log(msg: string, cls = '') { this.events.push({ t: this.t, msg, cls }); }

  dispatch() {
    if (this.amb) return;
    const lane = this.lanes[1];
    this.amb = { id: 0, lane, s: 0, v: 12, len: 6.2, w: 2.1, vmax: 17, acc: 3.5, amb: true, done: false, go: new Set(), a: 0 };
    lane.veh.push(this.amb); this.t0 = this.t;
    this.log('DISPATCH  Ambulance leaves Central Station → Hospital ER', 'b');
    if (!this.preempt) this.log('LifeLane OFF – ambulance obeys normal signals', 'a');
  }

  spawn(dt: number) {
    for (const l of this.lanes) {
      const r1 = l.r(), r2 = l.r(), r3 = l.r();
      if (!l.rate || r1 >= l.rate * dt) continue;
      const tail = l.veh[l.veh.length - 1];
      const type = r2 < 0.07 ? 'bus' : r2 < 0.25 ? 'van' : 'car';
      const len = type === 'bus' ? 9.5 : type === 'van' ? 5.6 : 4.4;
      if (tail && tail.s - tail.len < MINGAP + 9) continue;
      l.veh.push({ id: this.vid++, lane: l, s: 0, v: 9, len, w: type === 'bus' ? 2.5 : 1.9, type,
        vmax: 10 + 3.5 * ((r3 * 7919) % 1), col: CAR_COLS[Math.floor(r3 * CAR_COLS.length)], go: new Set(), a: 0 });
    }
  }

  moveVehicles(dt: number) {
    for (const l of this.lanes) {
      let lead: MockVehicle | null = null;
      for (const v of l.veh) {
        let vt = v.vmax;
        if (lead) {
          const gap = lead.s - lead.len - v.s - MINGAP;
          const vs = -B * TAU + Math.sqrt(B * B * TAU * TAU + lead.v * lead.v + 2 * B * Math.max(0, gap));
          vt = Math.min(vt, vs);
        }
        for (const st of l.stops) {
          if (v.s > st.s + 0.3 || v.go.has(st.j)) continue;
          const sg = this.sig[st.j].state(l.ap), d = st.s - v.s;
          if (sg === 'G') continue;
          if (sg === 'Y' && d < v.v * v.v / (2 * B) + 1) { v.go.add(st.j); continue; }
          vt = Math.min(vt, -B * TAU + Math.sqrt(B * B * TAU * TAU + 2 * B * Math.max(0, d - 0.2)));
        }
        if (v.amb && !v.done) {
          const d = ER_X - v.s;
          vt = Math.min(vt, -B * TAU + Math.sqrt(B * B * TAU * TAU + 2 * B * Math.max(0, d)));
        }
        const acc = v.amb ? (v.acc ?? 2.4) : 2.4, dv = vt - v.v;
        const nv = Math.max(0, dv > 0 ? v.v + Math.min(dv, acc * dt) : v.v + Math.max(dv, -BMAX * dt));
        v.a = (nv - v.v) / dt; v.v = nv; v.s += nv * dt;
        lead = v;
      }
      l.veh = l.veh.filter(v => v.s < l.len + 12 || v.amb);
    }
  }

  checkSafety() {
    const all: [MockVehicle, MockLane][] = [];
    for (const l of this.lanes) for (const v of l.veh) all.push([v, l]);
    for (const s of this.sig) {
      const open = APPR.filter(a => s.state(a) === 'G').length;
      if (open > this.maxOpen) this.maxOpen = open;
    }
    const A = this.amb;
    for (let i = 0; i < all.length; i++) {
      const [a, la] = all[i];
      for (let k = i + 1; k < all.length; k++) {
        const [b, lb] = all[k];
        const [ax, ay] = la.pt(a.s), [bx, by] = lb.pt(b.s);
        if (Math.abs(ax - bx) > 14 || Math.abs(ay - by) > 14) continue;
        const p = overlap(rectOf(a, la), rectOf(b, lb));
        if (p > 0.05) { const key = a.id + ':' + b.id; if (!this.pairs.has(key)) { this.pairs.add(key); this.coll++; } }
        if ((a === A || b === A) && A && !A.done) {
          const d = Math.hypot(ax - bx, ay - by) - (a.len + b.len) / 2 * (la === lb ? 1 : 0);
          this.minClear = Math.min(this.minClear, Math.max(0, d));
        }
      }
    }
  }

  frame() {
    const A = this.amb; let held = 0;
    for (const l of this.lanes) for (const v of l.veh) {
      if (v.amb || v.v > 0.4) continue;
      for (const st of l.stops) if (v.s <= st.s + 0.3 && st.s - v.s < 60) { if (this.sig[st.j].state(l.ap) !== 'G') { held++; break; } }
    }
    this.held = held;
    for (let j = 0; j < 3; j++) {
      const trk = this.trk[j], sg = this.sig[j];
      const noise = (this.rn() + this.rn() + this.rn() - 1.5) * 0.12;
      if (!A || A.done || A.s > X[j] + BOX + 5) { trk.c = 0; trk.p = 0; trk.t1 = trk.t2 = trk.t3 = false; trk.eta = 99; continue; }
      const d = Math.max(0, X[j] - STOPOFF - A.s);
      let p = 1 / (1 + Math.exp((d - MIC) / 28)) + noise;
      if (this.muted) p = 0.08 + Math.abs(noise) * 0.3;
      p = Math.max(0, Math.min(1, p));
      trk.p = p; trk.c = p >= PTH ? trk.c + 1 : 0;
      trk.t1 = trk.c >= 3;
      trk.t2 = true;
      trk.eta = d / Math.max(A.v, 14);
      trk.t3 = trk.eta <= LEAD;
      if (this.preempt && sg.mode === 'NORMAL' && trk.t1 && trk.t2 && trk.t3) {
        sg.begin('W');
        this.log(`J${j + 1}  verified (acoustic p=${p.toFixed(2)} · route ✓ · GPS ✓)  → PREPARING`, 'a');
      } else if (!this.preempt || (this.muted && trk.eta <= LEAD && sg.mode === 'NORMAL' && !this._fs[j])) {
        if (this.muted && this.preempt) { this._fs[j] = 1; this.log(`J${j + 1}  FAIL-SAFE: siren not confirmed → normal plan kept`, 'r'); }
      }
    }
  }

  step(dt: number) {
    const prev = this.sig.map(s => s.mode + s.phase);
    this.spawn(dt);
    this.sig.forEach(s => s.step(dt));
    this.moveVehicles(dt);
    this.t += dt; this.frameT += dt;
    if (this.frameT >= 0.5) { this.frameT -= 0.5; this.frame(); }
    const A = this.amb;
    this.sig.forEach((s, j) => {
      const m = prev[j].replace(/[GYAR]+$/, '');
      if (s.mode !== m) {
        const msgMap: Record<string, string> = {
          PREPARING: `J${j + 1}  other approaches → yellow → ALL RED`,
          SERVING: `J${j + 1}  SERVING – only the ambulance approach is GREEN`,
          RECOVERING: `J${j + 1}  ambulance clear → yellow → all-red → resume`,
          NORMAL: `J${j + 1}  back to NORMAL plan`,
        };
        const clsMap: Record<string, string> = { PREPARING: 'a', SERVING: 'g', RECOVERING: 'b', NORMAL: '' };
        this.log(msgMap[s.mode] ?? '', clsMap[s.mode] ?? '');
      }
      if (s.mode === 'SERVING' && (!A || A.done || A.s > X[j] + BOX + 5 || s.hold > MAXSERVE)) {
        if (s.hold > MAXSERVE) this.log(`J${j + 1}  FAIL-SAFE: 45 s max hold reached → release`, 'r');
        s.release();
      }
    });
    if (A && !A.done) {
      if (A.v < 0.3 && A.s < ER_X - 3) this.ambStopped += dt;
      if (A.s >= ER_X - 0.6 && A.v < 0.4) {
        A.done = true; A.arrive = this.t - this.t0;
        this.result = { duration: A.arrive, stopped: this.ambStopped };
        this.log(`ARRIVED  at hospital ER in ${A.arrive.toFixed(1)} s`, 'g');
      }
    }
    this.checkSafety();
  }

  toSnapshot(): Snapshot {
    const A = this.amb;
    const vehicles: Vehicle[] = [];
    for (const l of this.lanes) {
      for (const v of l.veh) {
        const [x, y] = l.pt(v.s);
        vehicles.push({
          id: v.id, edge: l.id, x, y,
          angle: l.hd * 180 / Math.PI,
          speed: v.v, len: v.len,
          kind: v.amb ? 'ambulance' : (v.type ?? 'car') as 'car' | 'van' | 'bus',
          braking: v.a < -0.6 || v.v < 0.3,
        });
      }
    }
    const junctions: Junction[] = this.sig.map((s, j) => ({
      id: `J${j + 1}` as 'J1' | 'J2' | 'J3',
      mode: s.mode,
      lights: { W: s.state('W'), N: s.state('N'), E: s.state('E'), S: s.state('S') },
      acoustic: { p: this.trk[j].p, consecutive: this.trk[j].c, tier1: this.trk[j].t1 },
      tier2_route: this.trk[j].t2,
      tier3_gps: this.trk[j].t3,
      eta_s: this.trk[j].eta < 90 ? this.trk[j].eta : null,
    }));
    return {
      t: this.t,
      running: !!(A && !A.done),
      preempt: this.preempt,
      vehicles,
      junctions,
      ambulance: A ? {
        x: A.lane.pt(A.s)[0], y: A.lane.pt(A.s)[1],
        angle: A.lane.hd * 180 / Math.PI,
        speed: A.v, s: A.s, done: A.done ?? false,
        elapsed: A ? this.t - this.t0 : 0,
        stopped_s: this.ambStopped,
        eta_hospital_s: Math.max(0, ER_X - A.s) / Math.max(A.v, 0.1),
      } : null,
      safety: { collisions: this.coll, max_open: this.maxOpen, held_at_red: this.held, min_clearance_m: this.minClear < 90 ? this.minClear : null },
      predictions: {
        eta: X.map((_, j) => ({ junction: `J${j + 1}`, predicted_s: this.trk[j].eta < 90 ? this.trk[j].eta : 0, actual_s: null })),
        route: { algo: 'astar', cost_s: 0, expanded: 0, edges: [] },
        model: { name: 'Mock Sim', version: '1.0.0', latency_ms: 0 },
      },
      events: this.events.map(e => ({ t: e.t, msg: e.msg, level: (({ g: 'ok', a: 'warn', b: 'info', r: 'error', '': 'info' } as Record<string,string>)[e.cls] ?? 'info') as 'info'|'ok'|'warn'|'error' })),
      result: this.result ? { with_s: this.result.duration, without_s: 0, saved_s: 0 } : null,
      demoData: true,
    };
  }
}

export function silentRun(seed: number, preempt: boolean, warm: number, muted: boolean): Sim {
  const s = new Sim(seed, preempt, { muted });
  while (s.t < warm) s.step(0.05);
  s.dispatch();
  while (!s.result && s.t < warm + 260) s.step(0.05);
  return s;
}
