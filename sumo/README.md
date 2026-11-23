# LifeLane SUMO Integration

This directory contains the SUMO traffic simulation files for the LifeLane ambulance signal preemption system.

## Files

| File | Description |
|------|-------------|
| `lifelane.nod.xml` | Network nodes: 4 traffic-light junctions (J1–J4), ambulance start, hospital |
| `lifelane.edg.xml` | Network edges: ambulance corridor + cross/background traffic edges |
| `lifelane.rou.xml` | Routes & vehicle types: ambulance + civilian background traffic flows |
| `lifelane.sumocfg` | SUMO config: ties net/route files together, sets TraCI port 8813 |
| `lifelane.net.xml` | **Generated** network file (run `generate_net.ps1` to create) |
| `traci_controller.py` | Python TraCI controller: runs simulation, preempts signals, writes `sim_state.json` |
| `sim_state.json` | **Runtime** state file read by the FastAPI backend WebSocket bridge |
| `generate_net.ps1` | Quick script to generate `lifelane.net.xml` via netconvert |
| `setup_sumo_demo.ps1` | Full first-time setup: installs pip packages + generates network |

## Network Layout

```
ambulance_start  -->  J1 ----------------------> J2 -->  hospital
                       |  ^                       |  ^
                       v  |                       v  |
                      J4  |                      J3  |
                       \--/                       \--/
```

- **Ambulance corridor:** `ambulance_start -> J1 -> J2 -> hospital`
- **Cross traffic:** `J4 <-> J1` and `J3 <-> J2`
- **Background loops:** `J4 <-> J3`

## First-Time Setup

```powershell
# From the LifeLane project root
cd sumo
.\setup_sumo_demo.ps1
```

This will:
1. Install `traci` and `sumolib` into the active Python environment
2. Run `netconvert` to generate `lifelane.net.xml`

## Running Manually

```powershell
# Activate venv first
.\.venv\Scripts\Activate.ps1

# Run the TraCI controller directly
python sumo\traci_controller.py
```

## How Signal Preemption Works

1. The `traci_controller.py` launches `sumo.exe` as a subprocess and connects via TraCI on port 8813.
2. Every simulation step (0.5s), it checks the ambulance's distance to J1 and J2.
3. When the ambulance is within **70 metres** of a junction, it calls `preempt_junction()`:
   - Forces the ambulance-approach phase to **GREEN** for 60 seconds
   - Cross-direction traffic gets **RED**
4. After the ambulance clears (distance > 70m), a **3-second recovery timer** starts, then `restore_junction()` resets normal cycling.
5. All state is written to `sim_state.json` every step.

## FastAPI Integration

The backend router at `backend/routers/sumo.py` provides:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/sumo/start` | POST | Launch `traci_controller.py` as subprocess |
| `/api/sumo/stop`  | POST | Terminate the simulation process |
| `/api/sumo/state` | GET  | Snapshot of current `sim_state.json` |
| `/api/sumo/ws`    | WS   | WebSocket pushing state every 500ms |

## Requirements

- **SUMO** installed at `C:\Users\hp\Desktop\SUMO\sumo-win64-1.28.0` (or `SUMO_HOME` env var)
- **Python packages:** `traci`, `sumolib` (install via `pip install traci sumolib`)
- **netconvert.exe** in SUMO bin directory (for network generation only)
