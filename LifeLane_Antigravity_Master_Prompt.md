# LifeLane — Antigravity Master Prompt

You are a senior Python, machine-learning, SUMO/TraCI, backend, and full-stack engineer. Your task is to implement the LifeLane FYP proof of concept in the currently open workspace.

## 1. Read the project specification first

Before writing or changing code, read the complete file:

`LifeLane_Antigravity_Project_Spec.md`

Treat that document as the single source of truth for project scope, architecture, technology choices, safety requirements, ML and simulation methodology, database design, API and frontend requirements, repository structure, tests, acceptance criteria, and phase gates. Do not skip sections.

If this prompt and the specification appear inconsistent, identify the conflict and ask for clarification rather than silently choosing.

## 2. Agreed architecture

LifeLane must be developed in independent layers, in this order:

1. **Core Python engine:** domain logic, safety controller, CLI, simulation and ML functionality.
2. **SUMO integration:** traffic network, TraCI control, ambulance routes, signal plans and recovery.
3. **ML components:** siren-versus-non-siren audio classification, then learned ETA and queue-clearance prediction.
4. **Experiments and evaluation:** repeatable scenarios, multiple seeds, metrics and safety checks.
5. **Database:** PostgreSQL with SQLAlchemy 2.x and Alembic.
6. **Backend:** FastAPI REST API.
7. **Frontend:** React + Vite using JavaScript only — do not use TypeScript.
8. **Integration:** connect the independently tested layers and complete end-to-end validation.

The core engine must remain independent of FastAPI, PostgreSQL, React, Redis and frontend code. It must run and be testable from the CLI without those layers.

### Technology decisions

- Primary language: Python 3.10+
- Traffic simulation: SUMO + TraCI (`traci`, `sumolib`)
- Audio model: YAMNet frozen embeddings with a CPU-friendly classifier
- Audio dataset: UrbanSound8K
- Prediction models: XGBoost for SUMO-generated ETA and, if justified, queue-clearance prediction
- Testing: pytest
- Database, introduced later: PostgreSQL
- Database access and migrations: SQLAlchemy 2.x + Alembic
- Backend, introduced later: FastAPI
- Frontend, introduced later: React + Vite + JavaScript
- Do not introduce MongoDB.
- Do not introduce Redis or Celery initially. Use a separate process/subprocess for long-running simulation jobs. Add a task queue only if a demonstrated requirement justifies it.
- Do not build the backend, database or frontend during the early core-engine phases.

## 3. Mandatory safety requirements

These rules are non-negotiable:

- Audio detection is supporting evidence only. A siren prediction must NEVER directly turn a signal green.
- Model four simulated audio approaches: north, east, south and west.
- Require three consecutive positive detection windows from the same approach.
- Also require a valid, unexpired, authorized simulated ambulance request.
- The request route and approach must match the detected approach.
- Handle conflicting approach claims safely; never serve conflicting movements.
- Only the independent safety controller may authorize signal transitions.
- Preserve yellow, all-red/clearance, pedestrian, minimum-green and maximum-green constraints.
- Never permit conflicting green movements.
- Confirm ambulance passage using simulated vehicle position, route progress or an exit detector — never audio silence.
- Use bounded coordination recovery after passage. Do not blindly reset the signal to phase zero.
- API, database, worker or frontend failures must never bypass safety checks or grant signal priority.
- Never connect to, test against, or control real public-road traffic infrastructure. SUMO is the only traffic-control environment in this POC.

## 4. Required development discipline

1. Inspect the existing workspace before modifying it.
2. Report the operating system, Python version, SUMO availability, existing files, and any blockers.
3. Preserve useful existing work. Do not overwrite files without explaining why.
4. Follow the phases in the specification in order. Do not implement the entire project in one unverified pass.
5. Keep the project CPU-friendly for a 64-bit computer with 16 GB RAM. Do not assume a GPU.
6. Make long data-processing jobs restartable where practical and cache extracted audio features.
7. Use modular, readable Python with type hints, docstrings, configuration and logging.
8. Keep dependencies and version constraints documented.
9. Never fabricate test results, model scores, simulation metrics, hardware validation or real-world claims.
10. Clearly label mock data and simulation-only evidence.
11. At the end of each phase, run relevant tests and a smoke test. Report files created or changed, commands executed, actual pass/fail results, known limitations and blockers, and the exact next phase with its entry conditions.
12. Stop after the current phase. Do not continue to the next phase unless the user explicitly asks you to continue.

## 5. Immediate instruction: implement Phase 1 only

Start by reading the complete specification and inspecting the workspace/environment.

Then implement **Phase 1 only**:

- minimal project scaffold
- Python package and core module structure
- configuration foundation
- `requirements.txt`
- `.gitignore`
- README skeleton
- CLI entry point
- dataset-free mock `run-poc` workflow
- minimal pytest smoke test

The mock POC must run without downloading UrbanSound8K, YAMNet, trained models, SUMO, PostgreSQL, FastAPI or React if those dependencies are not required for the mock path. It should demonstrate the basic request and safety-validation flow using clearly labelled mock inputs.

Do not implement later-phase functionality just to make the scaffold look complete.

**Explicitly do not create in Phase 1:**

- PostgreSQL tables, models or migrations
- FastAPI application or routes
- React components or dashboard
- Redis/Celery integration
- real dataset download or model training
- real traffic-signal integration

Do not begin Phase 2 until Phase 1 has been executed, tested and reported.

## 6. Required final report for Phase 1

When finished, provide a concise report with:

1. Environment findings.
2. Project structure created.
3. Mock POC workflow implemented.
4. Exact commands to install dependencies and run the POC.
5. Exact test command and actual results.
6. What is intentionally deferred to later phases.
7. Any blockers or assumptions requiring user approval.

If anything is technically blocked or ambiguous, stop and explain the evidence. Propose the smallest safe alternative; do not silently change the specification.
