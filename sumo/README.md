# SUMO Network — LifeLane 2×2 Grid

## Status

**Phase 3 — Not Yet Implemented**

The SUMO network files (`grid.net.xml`, `grid.rou.xml`, `grid.add.xml`, `grid.sumocfg`)
will be created in Phase 3.

## Planned Layout

```
J1 ──── J2
│         │
J3 ──── J4 ──→ Hospital (H1)
```

- **J1–J4**: Four signalized junctions.
- **Two ambulance routes**: J1→J2→J4 and J1→J3→J4.
- **Ordinary traffic**: Light / medium / heavy configurable demand.
- **Detectors**: On ambulance approaches for queue and vehicle counts.
- **Signal programs**: Coordinated fixed-time with explicit cycle, offsets,
  yellow, all-red, and pedestrian clearance phases.

## Requirements for Phase 3

1. Install SUMO: https://sumo.dlr.de/docs/Downloads.php
2. Set `SUMO_HOME` environment variable.
3. Install Python bindings: `traci` and `sumolib` (included with SUMO).

## Simulation Command (Phase 3)

```bash
sumo -c sumo/network/grid.sumocfg
```

Or with GUI:

```bash
sumo-gui -c sumo/network/grid.sumocfg
```

## Safety Notes

- SUMO is the ONLY traffic-control environment used in this POC.
- Never connect to or test against real public-road traffic infrastructure.
- No SUMO emergency "blue-light" behavior is used in main comparisons
  (decision documented here to ensure identical conditions across strategies).

