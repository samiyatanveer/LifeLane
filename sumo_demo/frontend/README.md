# LifeLane – React Frontend

Emergency green-corridor signal preemption demo.  
Exact visual match of `lifelane_demo.html`, built with **React 19 + Vite + TypeScript + Tailwind CSS**.

---

## Quick Start

```bash
cd frontend/app
pnpm install
pnpm dev          # http://localhost:5173
```

## Modes

| Mode | Command | Description |
|------|---------|-------------|
| **Mock** (default) | `pnpm dev` | Full physics run in the browser – no backend needed |
| **API** | `VITE_SOURCE=api pnpm dev` | Driven only by `/api/state` from FastAPI backend |

> Set `VITE_SOURCE=mock` explicitly or omit it entirely for mock mode.

## Build for Production

```bash
pnpm build        # outputs to dist/
pnpm preview      # preview the built app
```

## Type Check

```bash
pnpm typecheck    # tsc --noEmit – must pass with 0 errors
```

## Tests

```bash
pnpm test         # vitest run (8 unit tests)
pnpm test:watch   # watch mode
```

---

## Project Layout

```
frontend/app/
├── index.html
├── vite.config.ts        # Tailwind plugin + API proxy
├── vitest.config.ts
├── src/
│   ├── main.tsx          # React entry point
│   ├── App.tsx           # Root layout (header + canvas + aside)
│   ├── index.css         # CSS variables + global styles
│   ├── types.ts          # Shared TypeScript interfaces
│   ├── renderer.ts       # Canvas renderer (buildStatic + render)
│   ├── mock/
│   │   └── MockSource.ts # Sim + Sig classes (ported from lifelane_demo.html)
│   ├── hooks/
│   │   └── useSimulation.ts
│   ├── components/
│   │   ├── Header.tsx
│   │   ├── MapCanvas.tsx
│   │   ├── ControlsCard.tsx
│   │   ├── CorridorTrack.tsx
│   │   ├── JunctionCard.tsx
│   │   ├── SafetyMonitor.tsx
│   │   ├── ABResultCard.tsx
│   │   ├── EventLog.tsx
│   │   └── ModelPanel.tsx  ← new (acoustic charts, ETA table, model health)
│   └── __tests__/
│       └── simulation.test.ts
```

---

## Switching Data Sources

The switch is controlled by the `VITE_SOURCE` environment variable — no code changes needed:

```bash
# Mock mode (browser-only physics, no server)
pnpm dev

# API mode (requires backend at http://localhost:8080)
VITE_SOURCE=api pnpm dev
```

The `useSimulation` hook automatically falls back to MockSource (with `demoData: true` on the snapshot) if the API is unreachable.

---

## Design Constraints

- **Dark navy palette**: `--bg:#0a101c`, `--panel:#101a2b`, etc. — see `index.css`
- **Layout**: header → (canvas left + 384 px aside right)
- **Pre-rendered static city layer** (`buildStatic()`) + animated dynamic canvas — no per-vehicle DOM nodes
- **ONE approach green per junction** at any time — `chOne` chip turns red if violated
- Signal FSM: `NORMAL → PREPARING → SERVING → RECOVERING → NORMAL`

---

## Backend Integration

When `VITE_SOURCE=api`, the frontend expects:

- `GET /api/state` → `Snapshot` JSON (see [`docs/API.md`](../docs/API.md))
- `WS  /ws/state`  → push `Snapshot` every ~100 ms
- `POST /api/dispatch` → start ambulance run
- `POST /api/reset`    → reset simulation
- `POST /api/config`   → `{ preempt, traffic, muteSiren }`
