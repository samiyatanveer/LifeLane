# LifeLane — Antigravity Project Specification

## Project identity
**LifeLane: Route-Aware Ambulance Signal Preemption with Coordination Recovery**  
Educational FYP proof of concept using Python, SUMO/TraCI, audio classification, route planning, learned ETA/queue prediction, and a safety-constrained controller.

**Safety boundary:** Simulation and tabletop prototype only. Never connect to or control real public-road traffic signals.

## Core workflow

```text
Per-approach audio levels
        ↓
Siren suspected on one approach
        ↓
Repeated confirmation windows
        ↓
Authorized simulated ambulance request
        ↓
Learned ETA + queue-clearance prediction
        ↓
Route-aware corridor preparation
        ↓
Safe signal transition in SUMO
        ↓
Passage confirmation
        ↓
Bounded recovery
        ↓
Logs and evaluation
```

A siren prediction is supporting evidence only. It must NEVER directly turn a signal green. Priority requires:
1. A siren suspected on a specific approach.
2. Three consecutive positive windows from the same approach.
3. A valid, unexpired, authorized simulated ambulance request.
4. A matching route and approach at the junction.
5. Approval from an independent safety controller.

If the audio approach and request direction disagree, reject/hold for arbitration. If two approaches claim a siren simultaneously, do not automatically grant conflicting service.

## POC scope

### In scope
- Four simulated audio channels: north, east, south, west.
- UrbanSound8K binary classification: `siren` vs `non-siren`.
- Frozen YAMNet embeddings and a CPU-friendly classifier.
- Three-window same-approach confirmation.
- Mock authorized ambulance requests.
- Dijkstra or A* route planning.
- SUMO 2x2 grid with four signalized junctions J1–J4, alternative ambulance routes, ordinary traffic, and a hospital destination.
- XGBoost ETA regression trained on SUMO-generated data.
- Optional XGBoost queue-clearance regression if implemented and evaluated reliably.
- Route-aware preparation at upcoming junctions.
- Safe signal transitions and bounded recovery.
- Reproducible scenario comparisons, logs, tests, and evaluation.
- CLI-first demonstration. Streamlit is optional and must not delay a reliable simulation.

### Out of scope
- Real-world signal control or municipal infrastructure connections.
- Real ambulance dispatch, GPS, or hospital integrations.
- Claiming UrbanSound8K identifies an ambulance; it only supplies a `siren` class.
- Claiming SUMO-trained models prove real-road performance.
- Deep-learning inference on ESP32. For this POC, inference runs on the computer; ESP32 can later serve as an audio-capture/LED interface.
- Selecting a hospital from siren audio or inferred patient severity.

## Stack and machine constraints

### Core engine (build first)
- Python 3.10+
- SUMO + TraCI (`traci`, `sumolib`)
- TensorFlow / TensorFlow Hub; YAMNet: https://tfhub.dev/google/yamnet/1
- UrbanSound8K: https://zenodo.org/records/1203745
- `numpy`, `pandas`, `soundfile`, `librosa`, `scikit-learn`, `joblib`
- XGBoost; pytest
- CPU-only 64-bit machine, 16 GB RAM, 512 GB SSD. Do not assume CUDA/GPU. Avoid loading the full dataset into memory. Cache embeddings and make long-running processing restartable.

### Later application layers (do not build in the initial phases)
- **Backend API:** FastAPI + Pydantic. FastAPI exposes the stable engine through REST endpoints; it must not own or duplicate ML, route-planning, or signal-safety logic.
- **Database:** PostgreSQL as the primary persistent relational database, accessed through SQLAlchemy 2.x and managed with Alembic migrations. Use JSONB only for genuinely variable metadata, not as a substitute for relational tables.
- **Frontend:** React + Vite (JavaScript, not TypeScript) for a browser-based monitoring dashboard. Add only after the engine, SUMO workflow, API contracts, and persistence layer are stable.
- **Long-running simulations:** run in a separate worker process/job runner. Do not hold an HTTP request open while a full SUMO experiment runs. Start with a simple subprocess/job abstraction; add Redis/Celery or another queue only if demonstrated concurrency/reliability needs justify it.
- **No Redis initially:** PostgreSQL is sufficient for the first persistent version. Redis is optional future infrastructure, not a required dependency.

### Architecture boundary
The LifeLane engine must remain independently runnable and testable from the CLI without FastAPI, PostgreSQL, React, or Redis installed. Keep domain logic and safety-critical state transitions in `src/lifelane_engine/`. Application layers call the engine through explicit service interfaces/adapters; the engine must never import FastAPI routes, frontend code, database sessions, or web-framework objects. Database and API failures must not bypass or weaken the independent safety controller.

## Audio ML
1. Read official UrbanSound8K metadata.
2. Map `siren` to label 1 and every other class to 0.
3. Preserve official fold IDs and original `fsID` recording IDs.
4. Validate paths, filenames, duplicates, fold range, and source IDs. Raise an error if a source recording spans multiple folds.
5. Load WAV with `soundfile`; convert stereo to mono by averaging channels; resample to 16 kHz mono float32.
6. Check empty files, NaN, infinity, and unexpected amplitudes.
7. Do not aggressively denoise/trim or peak-normalize by default. Pad clips shorter than 0.96 seconds only when required.
8. Extract frozen YAMNet embeddings; average frame embeddings into one 1,024-dimensional vector per clip.
9. Save features, labels, fold, `fsID`, and filename to `data/processed/features.npz`; failures to `preprocessing_failures.csv`; manifest to `manifest.csv`.
10. Baseline classifier: `StandardScaler` + `LogisticRegression(class_weight="balanced")`.
11. Development split: folds 1–8 train, 9 validation, 10 held-out test. Optional official 10-fold CV.
12. Tune threshold on validation only, never on held-out test.
13. Report precision, recall, F1, confusion matrix, false-alarm rate, and a clearly defined detection latency. Save classifier/scaler with joblib.
14. Do not claim ambulance-specific siren recognition without a suitable labeled dataset and experiment.

### Per-approach selector
- Accept north/east/south/west simulated audio levels or probabilities.
- Smooth over time; use strongest rising siren evidence, not a single instantaneous loudness reading.
- Require 3 consecutive positive windows from the same approach.
- Treat close/simultaneous detections as conflict; do not silently choose one.
- Add cooldown and activation-rate limits.
- `audio_only_trigger_mode` may exist only as clearly labeled experimental mode. Default requires an authorized request too.

## Ambulance request and route planning
Mock request fields: ambulance ID, timestamp and expiry, current edge/location, heading/approach, intended route or origin/destination, selected hospital ID, emergency mode, and local simulated authorization status/token.

Validate fields, authorization, expiry, route consistency, and approach. A siren classifier does not prove ambulance identity.

Implement Dijkstra or A* with documented cost:

`route_cost = road_travel_time + expected_intersection_delay + congestion_penalty`

Closed/prohibited roads are unavailable. Use a mock hospital directory with ID, name, location, capabilities, and simulated availability. The authorized user/request selects the hospital; the siren model does not.

## SUMO network
Build a 2x2 grid with:
- J1, J2, J3, J4 signalized junctions.
- At least two ambulance routes, e.g. J1 → J2 → J4 and J1 → J3 → J4.
- Light, medium, heavy configurable ordinary-traffic demand.
- Distinguishable ambulance vehicle type/ID, e.g. `ambulance_1`.
- Coordinated fixed-time signal programs with explicit cycle, offsets, green, yellow, all-red/clearance, and pedestrian constraints where applicable.
- Detectors on ambulance approaches for queues and vehicle counts.
- A downstream-congestion scenario.
- No SUMO emergency blue-light behavior in main comparisons unless identical across all strategies; document the decision.
- Never hard-code phase indexes. Read phase meaning from network/configuration definitions.

## ETA and queue learning
Generate training data from many SUMO runs, multiple random seeds, and demand levels. Log every 0.5 or 1 simulation second.

Features may include: ambulance distance, speed, queue length (vehicles/metres), current phase, seconds to phase change, downstream occupancy, simulated time-of-day, demand level, junction and approach.

Targets:
- ETA = time from observation timestamp until ambulance reaches the junction stop line.
- Queue-clearance time = consistently defined time until sufficient downstream storage is available.

Save `data/sumo_logs/eta_dataset.csv` and `queue_dataset.csv`. Split by simulation run, e.g. seeds 1–70 train, 71–85 validation, 86–100 test. Never randomly split rows from the same run across train/test.

Train `XGBRegressor` for ETA; queue model is optional. One-hot encode categorical features. Report validation and held-out test MAE separately. Save models under `models/`.

**Limitation:** These models learn SUMO-generated patterns only; they do not establish real-road predictive accuracy.

## Corridor preparation
Start with straight-ahead movement only. Candidate formula:

```text
preparation_time =
    predicted_ETA
    - safe_transition_time
    - predicted_queue_clearance_time
    - safety_margin
```

If result <= 0, request preparation now; otherwise keep monitoring. After passage at one junction, predict ETA to the next and issue a time-limited request. Cancel safely if passage/arrival is not confirmed by predicted ETA plus expiry margin. The scheduler submits requests; it never commands green directly. If queue prediction is unavailable/unreliable, use a documented conservative fallback.

## Independent safety controller
Per-junction state machine:

```text
NORMAL
  ↓ siren suspected
SUSPECTED
  ↓ 3 consecutive positive windows
CONFIRMED
  ↓ valid authorized request + route/approach match
PREPARING
  ↓ safe transition complete
SERVING
  ↓ passage confirmed
EXITING
  ↓
RECOVERING
  ↓ alignment and queue recovery complete
NORMAL
```

Rules:
- ML and scheduler only submit requests; independent safety controller owns signal transitions.
- Only the validated ambulance approach may be served.
- Conflicting movements must never receive green simultaneously.
- Use configured yellow and all-red/clearance phases; never jump directly between conflicting greens.
- Respect pedestrian clearance, minimum/maximum green, and maximum service constraints.
- Confirm passage using vehicle position, route progress, or exit detector—not audio silence.
- Include request expiry, maximum service duration, cooldown, and activation-rate limits.
- On stale request, network/server failure, or simulation fault, expire/cancel and return to configured safe fallback.
- Add runtime assertions and tests for illegal transitions and conflicting greens.

## Bounded recovery
After passage:
1. End priority via the defined safe transition.
2. Serve delayed movements within configured maximum bounds.
3. Restore intended coordination/offset using the shared simulation clock.
4. Monitor queues and return to normal coordinated operation when alignment and recovery conditions are satisfied.

Do not restart at phase zero. Track timing/offset recovery duration separately from queue recovery duration. Prevent indefinite starvation of ordinary traffic.

## Experiments and metrics
Compare:
1. Normal coordinated fixed-time baseline.
2. Fixed-formula lead-time preparation.
3. Naive ETA (`distance / speed`, safely handle zero speed).
4. Learned ETA preparation.

Test light/medium/heavy demand and multiple seeds. Report:
- ambulance travel time and stopped time
- ordinary-vehicle mean and high-percentile delay (e.g. P95)
- maximum queue
- ETA MAE and queue-clearance MAE if applicable
- timing recovery and queue recovery duration separately
- early-preparation rate and late-arrival rate
- safety-rule violations (target: zero)

Define metrics in code and README. Do not report a single favorable run as conclusive.

## Logging
Use Python `logging`; do not silently swallow exceptions. Log timestamp, request/junction IDs, audio windows/scores, suspected/confirmed approach, conflicts, request accept/reject/expiry, route decisions/reroutes, predictions, preparation/expiry, every signal transition, passage confirmation, recovery, faults/fallbacks, and experiment metrics. Persist structured CSV/JSONL logs.

## Suggested repository layout

The initial phases create the core engine only. Add `api/`, `frontend/`, and persistence modules in their later phases; do not scaffold empty application layers prematurely.

```text
lifelane/
├── README.md
├── requirements.txt
├── .gitignore
├── config/settings.yaml
├── data/raw/UrbanSound8K/       # user downloads; never commit
├── data/processed/              # generated; never commit
├── data/sumo_logs/               # generated; never commit
├── models/                       # generated; never commit
├── reports/
├── scripts/
│   ├── download_instructions.md
│   ├── build_audio_features.py
│   ├── train_siren_classifier.py
│   ├── generate_sumo_eta_dataset.py
│   ├── train_eta_model.py
│   ├── train_queue_model.py
│   ├── run_experiment.py
│   └── evaluate_models.py
├── src/lifelane_engine/                 # framework- and database-independent core
│   ├── __init__.py
│   ├── config.py
│   ├── audio/{__init__.py,preprocess.py,feature_extractor.py,siren_classifier.py,approach_selector.py}
│   ├── ambulance/{__init__.py,request.py,route_planner.py}
│   ├── prediction/{__init__.py,eta_model.py,queue_model.py,dataset_builder.py}
│   ├── traffic/{__init__.py,corridor_scheduler.py,signal_controller.py,recovery.py}
│   ├── simulation/{__init__.py,sumo_runner.py,metrics.py,scenario.py}
│   └── main.py
├── sumo/network/{grid.net.xml,grid.rou.xml,grid.add.xml,grid.sumocfg}
├── sumo/README.md
├── api/                                  # Phase 8: FastAPI application and API tests
│   ├── app/{main.py,routers/,schemas/,services/,dependencies.py}
│   └── tests/
├── frontend/                             # Phase 9: React + Vite (JavaScript)
│   ├── src/{components/,pages/,services/,hooks/}
│   └── package.json
├── migrations/                           # Phase 7: Alembic migrations
└── tests/                                # core engine tests
    ├── test_audio_preprocess.py
    ├── test_approach_selector.py
    ├── test_route_planner.py
    ├── test_signal_controller.py
    ├── test_recovery.py
    └── test_eta_model.py
```

Adjust structure only for a clear engineering reason; keep modules small and responsibilities separate.

## Configuration
Create `config/settings.yaml` documenting dataset paths, 16 kHz sample rate, minimum 15,360 samples, YAMNet URL, baseline threshold 0.5, audio window duration, 3 confirmation windows, service limit, cooldown, activation-rate limit, SUMO path/config, simulation step, demand levels, seeds, ETA parameters, safety margin, preparation expiry, recovery settings, and log paths.

## Later application-layer requirements (implement only after core acceptance)

### PostgreSQL persistence — Phase 7
Use PostgreSQL as the primary database because LifeLane data is relational: simulation runs contain requests and events; requests reference routes/ambulances; junctions have approaches; signal events and predictions belong to specific runs and junctions; experiment metrics need reliable joins and aggregate SQL queries. PostgreSQL also supports JSONB for variable configuration or model metadata while preserving relational integrity.

Initial normalized tables should include:
- `simulation_runs`: run ID, scenario, seed, demand level, start/end timestamps, status, configuration snapshot and software/model versions.
- `ambulance_requests`: request ID, simulated ambulance ID, run ID, origin/destination, selected hospital, route, approach, created/expiry timestamps, authorization status and lifecycle status.
- `junctions`: junction ID, network/config reference and descriptive metadata.
- `signal_events`: run ID, junction ID, approach/movement, previous/new state, event timestamp and reason.
- `audio_detection_logs`: run ID, junction/approach, window timestamp, score, predicted class and confirmation state.
- `prediction_logs`: run/request/junction IDs, prediction type, predicted value, actual value when known, model version and timestamp.
- `experiment_metrics`: run ID, metric name, value, unit and aggregation context.
- `model_versions`: model type, version, artifact path/checksum, training dataset/split metadata and evaluation summary.

Use foreign keys, constraints, indexes for run/time/junction lookups, UTC timestamps, SQLAlchemy 2.x, and Alembic migrations. Store large audio files, feature arrays, model binaries and raw SUMO outputs on disk; store paths, checksums and metadata in PostgreSQL. Do not put large blobs into database rows. Do not persist every high-frequency simulation tick unless needed; define an explicit sampling/logging policy. Provide a database-free mock mode and core test suite at all times. Database access belongs in an adapter/repository layer outside the core domain engine.

### FastAPI backend — Phase 8
Create a separate `api/` application. Initial endpoints may include:
- `GET /health`
- `POST /simulation-runs` to validate and enqueue a configured simulation job
- `GET /simulation-runs/{run_id}` for status and summary
- `POST /ambulance-requests` for simulated authorized requests
- `GET /simulation-runs/{run_id}/events` for persisted event history
- `GET /simulation-runs/{run_id}/metrics` for results

Use Pydantic request/response schemas, dependency-injected service/repository interfaces, clear error handling, and API tests. Do not expose arbitrary shell commands, filesystem paths, or unrestricted SUMO configuration through endpoints. Do not let API handlers change signal phases directly. API handlers submit validated commands to the engine/service layer; only the independent safety controller can authorize transitions. Long-running simulations must run outside the request-response lifecycle in a separate process/worker. Return a job/run ID promptly and expose status/results endpoints. A simple local worker/subprocess implementation is sufficient initially; add a queue such as Redis/Celery only if requirements and measured load justify it. No Redis requirement for the first version.

### React dashboard — Phase 9
Use React + Vite with JavaScript (not TypeScript). Build a monitoring interface, not a real traffic-control console. Show simulation status, junctions, ambulance route/position, ETA, predicted queue clearance, signal state, siren evidence by approach, event timeline, and experiment metrics. Clearly label all data as simulated. The UI may request or cancel a simulated job through the API, but must never issue direct signal-phase commands. Use polling initially; add WebSockets/server-sent events only if a demonstrated need exists. Keep UI components separate from API client/service code.

### Full-stack integration — Phase 10
Connect React to FastAPI and FastAPI to PostgreSQL and the independent engine. Test valid and invalid requests, expired jobs, worker failure, database unavailability, stale events, and recovery. Fail closed: a frontend/API/database/worker outage must never produce a green signal or bypass safety checks in SUMO. Add authentication only if the demonstration requires multiple user roles; do not add unnecessary production infrastructure. Document local startup commands for each service and a one-command development workflow if practical.

## CLI and demo
Provide one entry point:

```bash
python -m lifelane_engine.main --mode <mode>
```

Modes: `train-audio`, `generate-eta-data`, `train-eta`, `run-poc`, `run-experiment`, `evaluate`.

`run-poc` must demonstrate:
1. Siren evidence + valid request → route selected and priority requested.
2. Siren evidence + invalid/expired request → rejected; no priority.
3. Non-siren evidence + valid request → no confirmation and no priority under default policy.
4. Ambulance passes → recovery → NORMAL.
5. Two conflicting approaches → no conflicting greens; documented hold/arbitration.
6. Stale request or simulated network failure → safe expiry.

The CLI demo must work with a small built-in/mock scenario even before UrbanSound8K is downloaded or models are trained.

## Tests and acceptance criteria
Use pytest for preprocessing, approach selection, request validation, route planning, controller state transitions, conflict prevention, recovery, and ETA model I/O.

Accept only if:
- CPU-only execution works without GPU.
- Mock CLI POC works without dataset/model downloads.
- Missing dataset/setup is explained clearly, not via opaque crash.
- SUMO config validates and documented simulation command works.
- Tests pass.
- Runtime and tests prevent conflicting greens.
- Siren alone never grants priority.
- Passage is vehicle/detector based, not silence based.
- Recovery is bounded and does not reset blindly to phase zero.
- Experiments are reproducible and split by simulation run.
- README distinguishes measured simulation results, assumptions, and limitations.

## Required README wording
Include verbatim:

> The current POC uses UrbanSound8K for siren versus non-siren audio classification. UrbanSound8K does not identify the emergency-vehicle type. Therefore, LifeLane treats siren detection as supporting evidence and requires a separate simulated authorized ambulance request before granting signal priority. The system is implemented for SUMO simulation and educational demonstration only.

Also include:

> The ETA and queue-clearance models are trained on SUMO-generated data. Results demonstrate feasibility within simulation and do not prove real-road performance.

README must also cover problem, scope/non-goals, architecture diagram, safety rules, installation, dataset download, preprocessing/YAMNet, training, SUMO setup, ETA data/model training, POC run, example output, metrics/comparisons, recovery, limitations, and future work.

## Antigravity implementation plan
Work incrementally; do not generate every module in one unverified pass. Each phase has a gate. Do not start a later phase until the current phase's acceptance criteria, tests and smoke test are reported truthfully. If a dependency or environment blocks a phase, stop and report the evidence and smallest safe alternative.

**Phase 1 — Inspect, scaffold and dataset-free mock POC:** inspect workspace/OS/Python/SUMO/existing files; report findings; create core package structure, config, requirements, `.gitignore`, README skeleton, CLI and mock `run-poc`. Include a small smoke test. Do not add FastAPI, PostgreSQL, React, Redis or dashboard code.

**Phase 2 — Independent safety and domain core:** implement typed requests, approach confirmation, authorization/expiry validation, route planner, state machine, conflict checks, safe transitions and bounded recovery. Write unit tests first. Prove siren evidence alone cannot cause green. Keep all domain logic independent of frameworks and persistence.

**Phase 3 — SUMO/TraCI integration:** build/validate 2x2 network, routes, detectors, signal programs and scenario runner; integrate TraCI; verify safe transitions and vehicle-based passage detection. Keep a working CLI path.

**Phase 4 — Audio ML:** metadata validation, preprocessing, YAMNet embeddings, classifier training, validation-only threshold selection and evaluation; configurable paths and restartable processing. Keep mock audio adapter and dataset-free demo.

**Phase 5 — ETA/queue prediction and corridor preparation:** generate multi-seed SUMO datasets with run IDs; implement run-level splits, XGBoost ETA and optional queue model, MAE reports and corridor integration. Queue model remains optional if target/data quality is weak.

**Phase 6 — Experiments and core acceptance:** run baseline/fixed-formula/naive-ETA/learned-ETA comparisons; export metrics; finish core README/troubleshooting. Confirm core engine and CLI are stable before application layers. Streamlit is not the planned frontend; the later dashboard uses React + Vite.

**Phase 7 — PostgreSQL persistence:** add PostgreSQL, SQLAlchemy 2.x, Alembic and repository/adapter layer. Implement normalized schema described above. Persist runs, requests, events, predictions, model metadata and metrics. Keep core engine usable without a database; add integration tests and migrations. Do not store large raw audio/model/SUMO files in PostgreSQL.

**Phase 8 — FastAPI backend:** create a separate FastAPI app with Pydantic schemas and REST endpoints for health, simulation jobs, requests, events and metrics. API must call engine services; it must not contain safety logic or manipulate signal phases. Run long jobs in a separate process/worker and return run IDs. Begin without Redis/Celery unless justified.

**Phase 9 — React frontend:** create a React + Vite dashboard in JavaScript (no TypeScript). Display simulated network, route, status, ETA, queue predictions, signal/event timeline and metrics. UI interacts only through the API; it cannot command signal phases. Label all data as simulation.

**Phase 10 — Full-stack integration and polish:** connect frontend, API, database and worker; test failure modes and fail-closed behavior; document setup, environment variables, migrations, startup and deployment. Add authentication, streaming updates or Redis only when justified by actual requirements.

At the end of every phase: run relevant tests and smoke test; report files changed, exact commands, actual pass/fail results, blockers and limitations. Never claim tests/simulations passed unless executed.

## Engineering rules
- Prefer a working vertical slice over broad nonfunctional scaffolding.
- Never fabricate accuracy, dataset results, simulation metrics, or hardware tests.
- Do not silently replace requested libraries/models. If incompatibility or CPU cost requires a change, explain evidence and propose the smallest alternative first.
- Keep optional components optional.
- Do not commit datasets, model binaries, logs, caches, or large generated files.
- Document exact install/version constraints, especially SUMO, TensorFlow, TensorFlow Hub, and Python.
- Keep safety decisions deterministic, inspectable, logged, and unit-tested.
