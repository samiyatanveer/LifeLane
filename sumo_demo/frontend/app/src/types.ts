// LifeLane shared TypeScript types

export type Approach = 'W' | 'N' | 'E' | 'S';
export type Light = 'G' | 'Y' | 'R';
export type Mode = 'NORMAL' | 'PREPARING' | 'SERVING' | 'RECOVERING';

export interface Vehicle {
  id: number;
  edge: string;
  x: number;
  y: number;
  angle: number;
  speed: number;
  len: number;
  kind: 'car' | 'van' | 'bus' | 'ambulance';
  braking: boolean;
}

export interface Junction {
  id: 'J1' | 'J2' | 'J3';
  mode: Mode;
  lights: Record<Approach, Light>;
  acoustic: { p: number; consecutive: number; tier1: boolean };
  tier2_route: boolean;
  tier3_gps: boolean;
  eta_s: number | null;
}

export interface AmbulanceInfo {
  x: number;
  y: number;
  angle: number;
  speed: number;
  s: number;
  done: boolean;
  elapsed: number;
  stopped_s: number;
  eta_hospital_s: number;
}

export interface Safety {
  collisions: number;
  max_open: number;
  held_at_red: number;
  min_clearance_m: number | null;
}

export interface EtaPrediction {
  junction: string;
  predicted_s: number;
  actual_s: number | null;
}

export interface RouteInfo {
  algo: 'astar' | 'dijkstra';
  cost_s: number;
  expanded: number;
  edges: string[];
}

export interface ModelInfo {
  name: string;
  version: string;
  latency_ms: number;
}

export interface SimEvent {
  t: number;
  msg: string;
  level: 'info' | 'ok' | 'warn' | 'error';
}

export interface ABResult {
  with_s: number;
  without_s: number;
  saved_s: number;
}

export interface Snapshot {
  t: number;
  running: boolean;
  preempt: boolean;
  vehicles: Vehicle[];
  junctions: Junction[];
  ambulance: AmbulanceInfo | null;
  safety: Safety;
  predictions: {
    eta: EtaPrediction[];
    route: RouteInfo;
    model: ModelInfo;
  };
  events: SimEvent[];
  result: ABResult | null;
  demoData?: boolean;
}

// Internal mock-only vehicle type (not in Snapshot)
export interface MockVehicle {
  id: number;
  lane: MockLane;
  s: number;
  v: number;
  len: number;
  w: number;
  vmax: number;
  acc?: number;
  col?: string;
  type?: 'car' | 'van' | 'bus';
  amb?: boolean;
  done?: boolean;
  go: Set<number>;
  a: number;
  arrive?: number;
}

export interface MockLane {
  k: number;
  id: string;
  ap: Approach;
  len: number;
  hd: number;
  rate: number;
  amb?: boolean;
  pt: (s: number) => [number, number];
  stops: { j: number; s: number }[];
  veh: MockVehicle[];
  r: () => number;
}
