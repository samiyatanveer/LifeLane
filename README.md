# LifeLane — Route-Aware Ambulance Signal Preemption with Coordination Recovery

**Version:** 2.0 — Phase 6 Complete (Core Engine)
**Status:** Simulation and Proof-of-Concept only

---

> **SAFETY DISCLAIMER — READ FIRST**
>
> LifeLane is an **educational Final Year Project (FYP) proof of concept**.
> It operates entirely within a simulation environment using SUMO (Simulation of Urban Mobility)
> or the built-in `MockSumoRunner`.
>
> **This system MUST NEVER be connected to or used to control real public-road traffic signals.**
> **It has no certification, safety audit, or regulatory approval for real-world deployment.**
> Doing so would be illegal and dangerous. All "junction coordination", "signal preemption",
> and "emergency response" described in this project are simulation-only.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture Summary](#architecture-summary)
3. [Core Safety Rules (Non-Negotiable)](#core-safety-rules)
4. [Phases Completed](#phases-completed)
5. [Setup Instructions](#setup-instructions)
6. [Running the System](#running-the-system)
7. [Test Suite](#test-suite)
8. [Project Structure](#project-structure)
9. [Known Limitations](#known-limitations)
10. [Phase 7+ Roadmap](#phase-7-roadmap)

---

## Project Overview

LifeLane is a route-aware ambulance signal preemption system that demonstrates how traffic
signal coordination can be prepared in advance of an emergency vehicle's arrival at each
junction along its route. Key capabilities (all simulated):

- **Siren detection** via audio ML (YAMNet embeddings + lightweight classifier)
- **Three-tier verification**: DETECTED → VERIFIED → AUTHORIZED
- **Ambulance registration & authentication** for both registered and unregistered vehicles
- **Temporary verification pathways** for unregistered ambulances (dispatch operator, ambulance app, license plate)
- **Dijkstra / A\* route planning** from ambulance GPS to selected hospital
- **Junction-wise ETA prediction** using XGBoost trained on simulation data
- **Route-aware corridor preparation** — junctions activated in route order
- **Safety-constrained signal controller** — never grants conflicting green signals
- **Bounded coordination recovery** — recovers from passage failures without hanging forever
- **SUMO 2×2 grid simulation** with junctions J1–J4 and hospital H1
- **Experiment comparison** across four coordination strategies

---

## Architecture Summary

```
Per-approach audio
       ↓
Siren detection (YAMNet + Logistic Regression)
       ↓  3 consecutive positive windows required
DETECTED (approach identified)
       ↓
Identity lookup
   ├─ Registered LifeLane device  → auto VERIFIED
   └─ Unregistered                → temp verification (DISPATCH_OPERATOR / AMBULANCE_APP / LICENSE_PLATE)
                                       ├─ Verified  → VERIFIED
                                       └─ Unverified → safe fallback (log, hold, no green)
       ↓
VERIFIED + authorized request + route/approach match
       ↓
AUTHORIZED (safety controller approves)
       ↓
GPS-aware junction-wise ETA (XGBoost)
       ↓
Route-aware corridor preparation (junctions in route order)
       ↓
Safe signal transition (SUMO / MockSumoRunner)
       ↓
Passage confirmation (vehicle position / detector)
       ↓
Bounded coordination recovery
       ↓
Logging + experiment metrics
```

### Module Map

| Package | Responsibility |
|---------|---------------|
| `lifelane_engine.dispatch` | Ambulance registry, authentication, GPS tracking, temp verification, session management, notifications |
| `lifelane_engine.ambulance` | Typed request models, Dijkstra/A* route planner |
| `lifelane_engine.audio` | Audio preprocessing, YAMNet feature extraction, siren classifier, approach selection |
| `lifelane_engine.traffic` | Signal controller state machine, corridor scheduler, coordination recovery |
| `lifelane_engine.simulation` | SUMO/TraCI runner, MockSumoRunner, scenario orchestrator, experiment metrics |
| `lifelane_engine.prediction` | ETA dataset builder, XGBoost ETA regressor, queue clearance model |
| `lifelane_engine.poc` | Mock POC runner (12 scenarios) |
| `lifelane_engine.config` | YAML config loader |
| `lifelane_engine.main` | CLI entry point |

---

## Core Safety Rules

These constraints are enforced in `signal_controller.py` and cannot be overridden by ML predictions:

1. **No conflicting green signals** — conflicting traffic movements are never simultaneously green.
2. **Mandatory yellow phase** before any green-to-red transition (configurable, default 3 s).
3. **Mandatory all-red clearance** after yellow (configurable, default 2 s).
4. **Minimum green duration** — no signal switches before minimum green time expires.
5. **Maximum green duration** — no approach held indefinitely; bounded by `max_green_s`.
6. **Siren alone is insufficient** — a detected siren cannot independently grant signal priority. AUTHORIZED state requires verified identity + authorized request + route/approach match.
7. **Bounded recovery** — corridor recovery has a configurable maximum delay; the system never hangs.
8. **No real infrastructure** — the engine imports no real traffic-control hardware interfaces.

---

## Phases Completed

### Phase 1 — Core Scaffolding and Mock POC ✅
- Project structure, config, logging
- Signal controller state machine (all safety constraints)
- Approach selector (3-consecutive-window rule)
- Corridor scheduler and bounded recovery
- Dataset-free mock POC (scenarios 1–6)
- **59 tests pass**

### Phase 2 — Dispatch Module and Three-Tier Verification ✅
- Ambulance registry (registered + unregistered pathways)
- Authenticator (hashed credentials, no plaintext)
- Session manager (60 s configurable timeout, duplicate detection)
- GPS tracker (real-time updates, stale detection)
- Temp verification (DISPATCH_OPERATOR, AMBULANCE_APP, LICENSE_PLATE)
- Notifier (acceptance, auth failure, route change, junction status, arrival)
- Dispatch service orchestrator
- Mock POC extended to 12 scenarios (7–12 cover dispatch/verification)
- **84 additional tests (143 total)**

### Phase 3 — SUMO Network and MockSumoRunner ✅
- 2×2 SUMO network: nodes, edges, routes, traffic lights, detectors (`sumo/network/`)
- Full TraCI wrapper (`sumo_runner.py`) with graceful fallback if SUMO not installed
- MockSumoRunner — physics-based vehicle kinetics, 2×2 grid, J1–J4 topology
- ScenarioRunner — orchestrates multi-seed experiments with configurable strategies
- ExperimentMetrics — captures travel time, queue length, safety violations
- **26 additional tests (169 total)**

> **Note:** `eclipse-sumo` pip install fails on this machine with SHA256 hash mismatch.
> All Phase 3+ integration uses MockSumoRunner (no SUMO/TraCI dependency at runtime).

### Phase 4 — Audio ML Pipeline ✅ (Real Data Trained)
- Audio preprocessing: resampling via scipy (16 kHz mono), 0.96 s windowed segments
- **Real YAMNet** frozen 1024-dim embeddings (TensorFlow Hub, CPU-only)
- Siren classifier: LogisticRegression + StandardScaler, threshold selected on validation set
- Resumable embedding cache (NPZ chunks + JSON index) — skips already-processed files
- Recording-level train/val/test split (SireNNet 70/15/15, seed=42); file-level split for Karachi
- 3-consecutive-positive-windows confirmation rule before siren alert
- **30 additional tests (199 total)**; 34 real-data pipeline tests added separately

**Datasets used (2026-11-11):**
| Dataset | Files | Siren | Non-siren | Source |
|---|---|---|---|---|
| SireNNet | 1,675 WAVs | 833 (ambulance) | 842 (firetruck/police/traffic) | `data/raw/sireNNet/` |
| Karachi Emergency Sirens | 1,834 WAVs | 932 (ambulance) | 902 (road_noise) | `data/raw/karachi/` |

> **Real-data model results (threshold = 0.600, selected on validation set):**
>
> | Test Set | Precision | Recall | F1 | False Alarm Rate |
> |---|---|---|---|---|
> | Karachi (276 samples) | 0.9655 | 0.8485 | **0.9032** | 2.78% |
> | SireNNet (250 samples) | 0.6163 | 0.9138 | **0.7361** | 17.19% |
> | Combined (526 samples) | 0.8168 | 0.8684 | **0.8418** | 11.01% |
>
> Train F1 = 0.9518 | Val F1 = 0.8678
> Model: `models/siren_classifier.joblib` | Scaler: `models/siren_scaler.joblib`

### Phase 5 — ETA and Queue Prediction ✅
- Synthetic ETA dataset generator (simulation-like features, leakage-free run-ID split)
- XGBoost ETA regressor: distance, speed, queue length, time-of-day, junction features
- Optional XGBoost queue clearance model
- Corridor integration: junction ETAs recalculated as ambulance progresses
- Save/load trained models (`models/eta_model.joblib`)
- **20 additional tests (219 total)**

> **XGBoost ETA results (synthetic data only):**
> Train MAE = 3.91 s | Val MAE = 5.02 s | Test MAE = 5.49 s | Naive baseline = 4.98 s
>
> XGBoost is marginally worse than naive on synthetic data because the synthetic formula
> IS the naive formula + noise — this is expected and documented. Real SUMO data would
> produce different results.

### Phase 6 — Experiments and Core Acceptance ✅
- Experiment runner comparing 4 strategies × 3 demand levels × 5 seeds (60 runs)
- Strategy variants: `baseline`, `fixed_formula`, `naive_eta`, `learned_eta`
- Model evaluation script — siren classifier + ETA model metrics written to `reports/`
- Full CLI (`main.py`) supporting all 6 modes
- **21 additional tests (240 total)**
- README (this file)

---

## Setup Instructions

### Requirements

- Python 3.11+
- Windows or Linux

### Install dependencies

```bash
pip install -r requirements.txt
```

**Core dependencies:**

```
numpy
pydantic>=2.0
pyyaml
scikit-learn
joblib
xgboost
pandas
soundfile
librosa
```

**Optional (not required for POC or tests):**

```
tensorflow-cpu   # for RealYAMNet; MockYAMNet used if absent
eclipse-sumo     # for real SUMO/TraCI; MockSumoRunner used if absent
```

### SUMO Network (optional)

SUMO network XML source files are in `sumo/network/`. If you have SUMO installed (`netconvert` available):

```bash
cd sumo/network
netconvert --node-files=grid.nod.xml --edge-files=grid.edg.xml \
           --tllogic-files=grid.tll.xml -o grid.net.xml
```

This generates `grid.net.xml` needed for real SUMO simulations. Not required for MockSumoRunner.

---

## Running the System

All modes use `python -m lifelane_engine.main --mode <mode>`.

From the project root, with `src/` on PYTHONPATH:

```bash
# Windows (PowerShell)
$env:PYTHONPATH = "d:\LIFELANE\src"
$env:PYTHONIOENCODING = "utf-8"

# Linux / Mac
export PYTHONPATH=$(pwd)/src
```

### Available Modes

#### `run-poc` — Mock POC (all 12 scenarios)
```bash
python -m lifelane_engine.main --mode run-poc
```
Runs the dataset-free mock proof-of-concept demonstrating all 12 scenarios:
- Scenarios 1–6: Signal safety (Phase 1) — green/yellow/red transitions, conflict prevention, recovery
- Scenarios 7–12: Dispatch/verification (Phase 2) — registered/unregistered ambulances, auth, GPS, routing

#### `train-audio` — Train siren classifier (synthetic fallback)
```bash
python -m lifelane_engine.main --mode train-audio
```
Trains LogisticRegression on **synthetic** YAMNet embeddings (for quick pipeline validation only).
Reports F1, precision, recall, false-alarm rate. Synthetic F1 ≈ 1.0 (Gaussian classes are perfectly separable).

#### `train-audio-real` — Train siren classifier on **real** audio datasets ⭐
```bash
python -m lifelane_engine.main --mode train-audio-real
```
Full real-data pipeline:
1. Builds manifest from SireNNet (`data/raw/sireNNet/`) + Karachi Emergency Sirens (`data/raw/karachi/`)
2. Extracts real YAMNet 1024-dim embeddings (cached in `data/processed/embeddings/` — resumable)
3. Trains LogisticRegression with class balancing; selects threshold on validation set
4. Evaluates on 3 test sets (Karachi, SireNNet, combined); saves report to `reports/audio_evaluation_real.txt`
5. Saves model: `models/siren_classifier.joblib` + `models/siren_scaler.joblib` + `models/siren_scaler_threshold.txt`

Requires: `tensorflow-cpu`, `tensorflow-hub`, `soundfile`, `scipy` (all in `requirements.txt`)

#### `demo-siren` — Live inference demo
```bash
# Quick auto demo (3 files from each class):
python scripts/demo_siren_detect.py

# Single file:
python scripts/demo_siren_detect.py --file data/raw/karachi/ambulance/ambulance1.wav

# Folder (up to N files):
python scripts/demo_siren_detect.py --folder data/raw/karachi/ambulance --limit 5
python scripts/demo_siren_detect.py --folder data/raw/karachi/road_noise --limit 5
python scripts/demo_siren_detect.py --folder data/raw/sireNNet/ambulance --limit 5
```
Outputs a table with P(siren), threshold, SIREN/NOT SIREN verdict and latency per file.
Requires: trained model (`models/siren_classifier.joblib`) and YAMNet TF Hub cache.

#### `generate-eta-data` — Generate ETA dataset
```bash
python -m lifelane_engine.main --mode generate-eta-data
```
Generates synthetic ETA training dataset. Saves to `data/sumo_logs/eta_dataset_synthetic.csv`.
For real data, run SUMO scenarios first (requires `eclipse-sumo`).

#### `train-eta` — Train XGBoost ETA model
```bash
python -m lifelane_engine.main --mode train-eta
```
Trains XGBoost regressor on synthetic ETA data. Reports MAE vs naive baseline. Saves `models/eta_model.joblib`.

#### `run-experiment` — Strategy comparison
```bash
python -m lifelane_engine.main --mode run-experiment
```
Runs 60 experiments (4 strategies × 3 demand levels × 5 seeds). Saves `reports/experiment_results.csv`.
Prints summary table.

#### `evaluate` — Model evaluation report
```bash
python -m lifelane_engine.main --mode evaluate
```
Evaluates siren classifier and ETA model. Writes full report to `reports/model_evaluation.txt`.

#### Log level control
Add `--log-level WARNING` to suppress INFO logs:
```bash
python -m lifelane_engine.main --mode run-poc --log-level WARNING
```

---

## Test Suite

```bash
# From project root (no PYTHONPATH needed — pytest.ini handles it)
python -m pytest tests/ -q
```

**Expected result: 240 passed**

Run with verbose output:
```bash
python -m pytest tests/ -v --tb=short
```

Run a specific phase:
```bash
python -m pytest tests/test_signal_controller.py -v       # Phase 1
python -m pytest tests/test_dispatch_service.py -v        # Phase 2
python -m pytest tests/test_mock_sumo.py -v               # Phase 3
python -m pytest tests/test_audio_pipeline.py -v          # Phase 4
python -m pytest tests/test_eta_pipeline.py -v            # Phase 5
python -m pytest tests/test_phase6_experiments.py -v      # Phase 6
```

### Test files by phase

| Phase | Test Files | Tests |
|-------|-----------|-------|
| 1 | `test_signal_controller.py`, `test_approach_selector.py`, `test_corridor_scheduler.py`, `test_recovery.py`, `test_route_planner.py`, `test_mock_poc.py` | 59 |
| 2 | `test_verification_state.py`, `test_registry.py`, `test_authenticator.py`, `test_session_manager.py`, `test_gps_tracker.py`, `test_temp_verification.py`, `test_dispatch_service.py` | 84 |
| 3 | `test_mock_sumo.py` | 26 |
| 4 | `test_audio_pipeline.py` | 30 |
| 5 | `test_eta_pipeline.py` | 20 |
| 6 | `test_phase6_experiments.py` | 21 |
| **Total** | | **240** |

---

## Project Structure

```
d:\LIFELANE\
├── README.md                          # This file
├── LifeLane_Antigravity_Project_Spec_v2.md  # Authoritative spec
├── requirements.txt                   # Python dependencies
├── pytest.ini                         # Test configuration
├── config/
│   └── settings.yaml                  # System configuration
├── src/
│   └── lifelane_engine/
│       ├── __init__.py
│       ├── main.py                    # CLI entry point (6 modes)
│       ├── config.py                  # Config loader
│       ├── ambulance/
│       │   ├── request.py             # Typed ambulance request models
│       │   └── route_planner.py       # Dijkstra / A* route planner
│       ├── audio/
│       │   ├── approach_selector.py   # 3-consecutive-window approach selection
│       │   ├── feature_extractor.py   # YAMNet (real + mock fallback)
│       │   ├── preprocess.py          # Audio preprocessing pipeline
│       │   └── siren_classifier.py    # LogisticRegression siren classifier
│       ├── dispatch/
│       │   ├── authenticator.py       # Credential verification (hashed)
│       │   ├── dispatch_service.py    # Orchestration service
│       │   ├── emergency_request.py   # Request lifecycle models
│       │   ├── gps_tracker.py         # Real-time GPS updates, stale detection
│       │   ├── notifier.py            # Operator notifications
│       │   ├── registry.py            # Ambulance registry (registered + temp)
│       │   ├── session_manager.py     # Session timeout, duplicate detection
│       │   ├── temp_verification.py   # Temp verification pathways
│       │   └── verification_state.py  # DETECTED / VERIFIED / AUTHORIZED states
│       ├── poc/
│       │   └── mock_poc.py            # 12 scenarios, no external dependencies
│       ├── prediction/
│       │   ├── dataset_builder.py     # Synthetic + SUMO ETA dataset builder
│       │   ├── eta_model.py           # XGBoost ETA regressor
│       │   └── queue_model.py         # XGBoost queue clearance model
│       ├── simulation/
│       │   ├── metrics.py             # ExperimentMetrics NamedTuple
│       │   ├── mock_sumo.py           # MockSumoRunner (no SUMO required)
│       │   ├── scenario.py            # ScenarioRunner, strategy dispatch
│       │   └── sumo_runner.py         # Full TraCI wrapper + graceful fallback
│       └── traffic/
│           ├── corridor_scheduler.py  # Route-aware corridor preparation
│           ├── recovery.py            # Bounded coordination recovery
│           └── signal_controller.py   # Safety-constrained signal state machine
├── tests/                             # 240 unit/integration tests
├── scripts/
│   ├── run_experiment.py              # Phase 6 experiment runner
│   └── evaluate_models.py             # Phase 6 model evaluation
├── sumo/
│   └── network/
│       ├── grid.nod.xml               # SUMO junction nodes (J1–J4, H1)
│       ├── grid.edg.xml               # SUMO road edges
│       ├── grid.tll.xml               # Traffic light programs
│       ├── grid.rou.xml               # Vehicle routes and flows
│       ├── grid.add.xml               # E2 loop detectors
│       └── grid.sumocfg               # SUMO simulation config
├── models/
│   └── eta_model.joblib               # Trained XGBoost ETA model
├── data/
│   └── sumo_logs/
│       └── eta_dataset_synthetic.csv  # Synthetic ETA training data
└── reports/
    ├── experiment_results.csv         # Phase 6 experiment comparison
    └── model_evaluation.txt           # Phase 6 model evaluation report
```

---

## Known Limitations

### SUMO / TraCI not installed
`eclipse-sumo` pip installation failed with SHA256 hash mismatch on the development machine.
All SUMO-dependent code falls back to `MockSumoRunner` automatically. The SUMO network XML
source files are correctly authored in `sumo/network/` and will work once SUMO is installed.

### TensorFlow not installed
`RealYAMNet` (TensorFlow Hub) is not available. `MockYAMNet` generates random 521-dimensional
Gaussian embeddings instead. The pipeline, classifier, and all downstream logic are fully tested.

### UrbanSound8K dataset not available
All siren classifier metrics use synthetic Gaussian data. Reported F1=1.0 / FAR=0.0 is
expected on perfectly-separable Gaussian classes — it does **not** represent real audio
detection performance. The pipeline is designed for UrbanSound8K once obtained.

### Synthetic ETA dataset
XGBoost ETA results (MAE=5.49 s vs naive baseline=4.98 s) are on synthetic data. The synthetic
formula IS the naive formula + noise, so XGBoost being marginally worse than naive is expected.
Real SUMO simulation data would produce different (and meaningful) results.

### MockSumoRunner physics
MockSumoRunner simulates vehicle kinetics on a fixed 2×2 grid topology. Metrics (travel time,
queue length) are approximate. Only real SUMO/TraCI provides traffic-accurate simulation.

### Experiment results
All experiment_results.csv values are from MockSumoRunner with Gaussian noise. They demonstrate
that the pipeline runs correctly across 60 trials but do not represent real coordination performance.

### Windows console encoding
On Windows PowerShell, set `$env:PYTHONIOENCODING = "utf-8"` before running the CLI
to avoid Unicode display issues in the mock POC output.

---

## Phase 7+ Roadmap

These phases are **explicitly out of scope** for the current implementation.
They are planned in the specification and architecture but not implemented.

| Phase | Description |
|-------|-------------|
| 7 | PostgreSQL persistence — Replace in-memory stores with real database |
| 8 | FastAPI REST layer — HTTP endpoints for dispatch, GPS, hospitals, routes |
| 9 | React dashboard — Live simulation map, ambulance tracker, signal status |
| 10 | Real dataset training — UrbanSound8K + real SUMO simulation runs |

---

## Configuration

Edit `config/settings.yaml` to tune key parameters:

```yaml
dispatch:
  verification_timeout_s: 60      # Max seconds to complete verification
  session_max_age_s: 3600         # Session expiry
  gps_stale_threshold_s: 30       # GPS staleness detection

signal:
  yellow_duration_s: 3            # Mandatory yellow phase
  all_red_duration_s: 2           # All-red clearance
  min_green_s: 5                  # Minimum green before switching
  max_green_s: 120                # Maximum green hold

corridor:
  max_recovery_delay_s: 60        # Bounded recovery max delay
```

---

## Academic / Research Use

If using this project for academic reference:

- All ML results are on synthetic data unless explicitly noted otherwise.
- No real-world traffic signal hardware was used.
- The safety controller is a software simulation only.
- The system has not been validated for real emergency response.

---

## Authors and Acknowledgements

LifeLane FYP project.  
Architecture and implementation: LifeLane development team.  
Specification: `LifeLane_Antigravity_Project_Spec_v2.md`.

**Libraries used:** Python, NumPy, scikit-learn, XGBoost, pandas, librosa, soundfile, Pydantic, PyYAML, joblib.  
**Simulation:** SUMO (Simulation of Urban MObility) — https://eclipse.dev/sumo/  
**Audio features:** YAMNet (Google) — https://tfhub.dev/google/yamnet/1  
**Dataset (planned):** UrbanSound8K — https://urbansounddataset.weebly.com/urbansound8k.html
