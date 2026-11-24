# LifeLane – API Contract

All endpoints are served by FastAPI at `http://localhost:8080`.

---

## REST Endpoints

### `GET /api/state`
Returns the current simulation snapshot.

**Response:** [`Snapshot`](#snapshot-type)

---

### `POST /api/dispatch`
Dispatches the ambulance from the start edge.

**Request body** (optional):
```json
{ "hospital_id": "H1", "start_edge": "e_west_j1" }
```
**Response:** `{ "ok": true }`

---

### `POST /api/reset`
Resets the simulation and all statistics.

**Response:** `{ "ok": true }`

---

### `POST /api/config`
Updates runtime configuration.

**Request body:**
```json
{
  "preempt": true,
  "traffic": true,
  "mute_siren": false
}
```
**Response:** `{ "ok": true }`

---

### `GET /api/history`
Returns the last N snapshots (for replays/charts).

**Response:** `Snapshot[]`

---

### `POST /api/predict`
Requests an ML ETA prediction for a given feature vector.

**Request body:**
```json
{ "features": [1.0, 190.0, 15.0, 0.85] }
```
**Response:**
```json
{ "predicted_eta_s": 12.3, "confidence": 0.91 }
```

---

## WebSocket

### `WS /ws/state`
Streams `Snapshot` JSON at ~10 Hz (100 ms intervals).  
Connect with:
```js
const ws = new WebSocket('ws://localhost:8080/ws/state');
ws.onmessage = e => { const snap = JSON.parse(e.data); /* ... */ };
```

---

## Snapshot Type

```typescript
type Approach = 'W' | 'N' | 'E' | 'S';
type Light    = 'G' | 'Y' | 'R';
type Mode     = 'NORMAL' | 'PREPARING' | 'SERVING' | 'RECOVERING';

interface Vehicle {
  id: number;
  edge: string;           // SUMO edge id
  x: number; y: number;  // world coords (metres)
  angle: number;          // heading degrees
  speed: number;          // m/s
  len: number;            // metres
  kind: 'car' | 'van' | 'bus' | 'ambulance';
  braking: boolean;
}

interface Junction {
  id: 'J1' | 'J2' | 'J3';
  mode: Mode;
  lights: Record<Approach, Light>;
  acoustic: { p: number; consecutive: number; tier1: boolean };
  tier2_route: boolean;
  tier3_gps: boolean;
  eta_s: number | null;   // seconds until ambulance arrives, null if unknown
}

interface AmbulanceInfo {
  x: number; y: number; angle: number;
  speed: number;          // m/s
  s: number;              // distance travelled along route (m)
  done: boolean;
  elapsed: number;        // seconds since dispatch
  stopped_s: number;      // cumulative stopped time (s)
  eta_hospital_s: number; // estimated seconds to hospital
}

interface Safety {
  collisions: number;
  max_open: number;       // max simultaneous green approaches (must be ≤ 1)
  held_at_red: number;    // vehicles currently stopped at red
  min_clearance_m: number | null;  // closest other vehicle to ambulance (m)
}

interface Snapshot {
  t: number;              // simulation time (s)
  running: boolean;
  preempt: boolean;       // LifeLane ON/OFF
  vehicles: Vehicle[];
  junctions: Junction[];
  ambulance: AmbulanceInfo | null;
  safety: Safety;
  predictions: {
    eta: { junction: string; predicted_s: number; actual_s: number | null }[];
    route: { algo: 'astar' | 'dijkstra'; cost_s: number; expanded: number; edges: string[] };
    model: { name: string; version: string; latency_ms: number };
  };
  events: { t: number; msg: string; level: 'info' | 'ok' | 'warn' | 'error' }[];
  result: { with_s: number; without_s: number; saved_s: number } | null;
  demoData?: boolean;     // true when frontend is using MockSource fallback
}
```

---

## Signal State Machine

```
NORMAL → PREPARING → SERVING → RECOVERING → NORMAL
```

| Mode        | Color    | Meaning |
|-------------|----------|---------|
| NORMAL      | `#8a9bb8` | Normal green-cycle (W→N→E→S) |
| PREPARING   | `#f59e0b` | Transitioning to ambulance green (yellow→all-red in progress) |
| SERVING     | `#22c55e` | Ambulance direction is GREEN, all others RED |
| RECOVERING  | `#38bdf8` | Ambulance cleared, yellow→all-red→resume normal cycle |

---

## Safety Rules (enforced in backend)

1. **ONE green** at a time per junction (`max_open ≤ 1`)
2. All transitions: `GREEN → YELLOW (3 s) → ALL-RED (1–2 s) → next GREEN`
3. Normal vehicles stop at the red stop-line; they never overlap the ambulance
4. Fail-safes: siren muted → no preemption; 45 s max hold → auto-release
