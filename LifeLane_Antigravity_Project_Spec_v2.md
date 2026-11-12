# LifeLane — Project Specification v2
# Route-Aware Ambulance Signal Preemption with Coordination Recovery
# Ambulance Identity, Dispatch Management & Inclusive Emergency Access

**Version:** 2.0 — Extends v1 with Dispatch Management and Unregistered Ambulance Support  
**Status:** Documentation / Architecture update — No new code has been written beyond Phase 1.  
**Safety boundary:** Simulation and tabletop prototype only. Never connect to or control real public-road traffic signals.

---

## What Changed from v1

Two expansion requests are integrated here. Neither discards v1:

| Addition | Origin |
|----------|--------|
| Ambulance Registry, Authentication, GPS Tracking, Dispatch workflow, Hospital Directory, Junction-wise ETA, Dynamic rerouting, Notifications | Expansion request 1 (Dispatch Management) |
| Unregistered ambulance pathway, Three-tier verification model (DETECTED / VERIFIED / AUTHORIZED), Safe fallback for unverified, Temp verification | Expansion request 2 (Inclusive Access) |

Everything in v1 — audio ML, YAMNet, UrbanSound8K, SUMO 2×2 grid, XGBoost ETA, safety controller state machine, bounded recovery, experiments, PostgreSQL, FastAPI, React — is **fully preserved**. No v1 requirement is removed.

---

## Project Identity (Unchanged)

**LifeLane: Route-Aware Ambulance Signal Preemption with Coordination Recovery**  
Educational FYP proof of concept using Python, SUMO/TraCI, audio classification, route planning,
learned ETA/queue prediction, a safety-constrained controller, and an inclusive dispatch system
supporting both registered and unregistered ambulances.

---

## Updated Core Workflow

```text
Per-approach audio levels
        ↓
Siren suspected on one approach
        ↓
Repeated confirmation windows  →  DETECTED (approach identified)
        ↓
Ambulance identity lookup
  ├── Registered device?   → automatic VERIFIED
  └── Unregistered?        → temporary verification pathway
                                 ├── Verified  → VERIFIED
                                 └── Unverified → safe fallback (log, hold, alert)
        ↓
VERIFIED + valid unexpired authorized request + route/approach match
        ↓
AUTHORIZED (safety controller approves)
        ↓
GPS-aware junction-wise ETA + queue-clearance prediction
        ↓
Route-aware corridor preparation (junctions in route order)
        ↓
Safe signal transition in SUMO
        ↓
Passage confirmation (vehicle position / detector)
        ↓
Bounded coordination recovery
        ↓
Logs, notifications and evaluation
```

### Unchanged Safety Axioms from v1

A siren prediction is supporting evidence only. It must NEVER directly turn a signal green.
Signal priority requires ALL of:
1. Siren detected and confirmed on a specific approach (3 consecutive positive windows).
2. Ambulance identity VERIFIED through a registered or temporary pathway.
3. A valid, unexpired, AUTHORIZED simulated request with matching route and approach.
4. Approval from the independent safety controller.
5. Yellow + all-red transition before any green.
6. No conflicting green movements.

If the audio approach and request direction disagree → reject/hold.  
If two approaches claim a siren simultaneously → CONFLICT; do not grant either automatically.  
**DETECTED alone never grants priority. VERIFIED alone never grants priority.**

---

## Three-Tier Verification Model

This is the central new concept. Every ambulance progresses through distinct, logged states:

```
UNDETECTED
    ↓  (siren detected, 3 consecutive windows, approach identified)
DETECTED
    ↓  (identity verified: registered device OR temporary pathway)
VERIFIED
    ↓  (safety controller approves: request valid, route matches, approach matches)
AUTHORIZED
    ↓  (signal priority active)
SERVING / PASSAGE / RECOVERING
```

### State Rules

| State | What It Means | Can Grant Green? | Notes |
|-------|--------------|-----------------|-------|
| UNDETECTED | No siren evidence | No | Normal operation |
| DETECTED | Siren confirmed on approach | **No** | Audio only; identity unknown |
| VERIFIED | Identity/emergency confirmed | **No** | Still needs safety-controller approval |
| AUTHORIZED | Full safety check passed | Yes, via safe transition | All five conditions satisfied |

### Safe Fallback for DETECTED-but-Unverified

When a siren is DETECTED but identity cannot be verified within a configured timeout:
1. **Do not grant priority.** Do not advance to AUTHORIZED.
2. **Do not silently ignore.** Log the detection with full timestamp and approach.
3. **Generate a simulated operator alert** (notification log; mock in POC).
4. **Hold at DETECTED** until: (a) verification succeeds, or (b) timeout expires.
5. On timeout: reset to UNDETECTED; log as "unverified siren event".
6. This constitutes a documented "unresolved emergency" in the event log.

This fallback is safe (no false green), inclusive (does not discard the ambulance), and auditable.

---

## Ambulance Types and Verification Pathways

### 1. Registered Ambulances

A registered ambulance has a pre-existing entry in the LifeLane Ambulance Registry.

**Identity fields stored in registry:**
- `lifelane_id`: System-assigned unique ID
- `registration_number`: Vehicle registration plate
- `service_name`: Emergency service / operator
- `device_id`: Identifier of onboard LifeLane-compatible device
- `credential_hash`: Hashed credential (never store plaintext)
- `registration_status`: ACTIVE / SUSPENDED / REVOKED
- `registered_at`, `updated_at`

**Verification pathway:**
1. Onboard device presents `device_id` + credential.
2. Registry authenticator verifies credential hash.
3. Registration status checked: ACTIVE required.
4. If valid → state advances to VERIFIED immediately.
5. Authentication failure → treated as unregistered; temporary pathway offered.

**Additional registered capabilities (when GPS device is present):**
- Automatic periodic GPS updates.
- Automatic hospital destination submission from dispatch system.
- Session-based authenticated communication.

### 2. Unregistered Ambulances

An unregistered ambulance is not in the LifeLane registry but may be a legitimate emergency vehicle.
Permanent registration must NOT be a prerequisite for emergency assistance.

**Temporary verification pathway** (simulated in POC; all three are mocked):

| Method | Description | Trust Level | POC Simulation |
|--------|-------------|-------------|----------------|
| Dispatch operator confirmation | A dispatch operator (human or automated) confirms the ambulance ID and emergency via a separate channel | HIGH | Simulated via mock operator approval token |
| Ambulance app submission | Operator submits identity, GPS, and hospital via a mobile/web form | MEDIUM | Simulated via structured data payload |
| License plate cross-reference | System attempts to match the announced registration number against a secondary database | LOWER | Simulated via mock lookup returning known/unknown |

**Fields collected in temporary verification:**
- `temp_id`: System-generated temporary ID for this incident
- `announced_registration`: Vehicle registration number as announced/submitted
- `verification_method`: One of the three methods above
- `verifying_operator_id`: Simulated operator who confirmed
- `gps_location`: Current location (may be approximate or manually entered)
- `hospital_id`: Selected destination hospital
- `emergency_description`: Brief text description
- `verification_token`: Time-limited token issued on success
- `verified_at`, `expires_at`
- `verification_confidence`: HIGH / MEDIUM / LOW (from method used)

**Trust-level effects:**
- HIGH: Same workflow as registered ambulance; request proceeds normally.
- MEDIUM: Same workflow; slightly shorter request expiry (configurable).
- LOW: Same workflow; logged as lower-confidence; flagged in experiment metrics.
- All three: subject to identical safety controller rules; no shortcut to green.

**Offer of permanent registration:**
After a successful temporary verification event, the system logs a recommendation
for permanent registration. This is informational only; it does not block the current emergency.

---

## Dispatch Module Architecture

A new `dispatch/` sub-package is added to `lifelane_engine`. It contains all domain logic
for registration, authentication, GPS, sessions, requests, verification, and notifications.

**Architecture boundary:** The dispatch module must remain framework- and database-independent.
It must never import FastAPI, PostgreSQL sessions, or React code.
Application layers call it through explicit service interfaces.

### Module Responsibilities

```
src/lifelane_engine/dispatch/
├── __init__.py
├── registry.py             # Ambulance Registry (in-memory mock; PostgreSQL in Phase 7)
├── authenticator.py        # Credential verification for registered ambulances
├── gps_tracker.py          # GPS location updates, staleness detection, route deviation
├── emergency_request.py    # Emergency request lifecycle (extends existing request.py)
├── temp_verification.py    # Unregistered ambulance temporary verification pathway
├── verification_state.py   # VerificationLevel enum + VerificationRecord dataclass
├── session_manager.py      # Authenticated session management (registered ambulances)
├── notifier.py             # Operator notifications (mock; real integration later)
└── dispatch_service.py     # Orchestration facade: ties above modules together
```

### Module Descriptions

**`registry.py`**
- `AmbulanceRegistry`: in-memory dict-backed store (Phase 2), PostgreSQL-backed in Phase 7.
- Methods: `register()`, `lookup_by_device_id()`, `lookup_by_registration()`,
  `update_status()`, `list_all()`.
- Never stores plaintext credentials. Uses `hashlib.sha256` for mock hashing in Phase 2.
- Provides a `MockRegistry.build_default()` factory for POC and tests.

**`authenticator.py`**
- `AmbulanceAuthenticator`: verifies device credentials against registry.
- Returns `AuthResult(success, ambulance_id, reason)`.
- Enforces: status must be ACTIVE, credential hash must match, session must not be duplicated.
- On failure: logs reason; does NOT advance verification state.

**`gps_tracker.py`**
- `GpsUpdate`: dataclass with `ambulance_id`, `latitude`, `longitude`,
  `speed_ms`, `heading_deg`, `timestamp`, `source` (DEVICE / MANUAL / SIMULATED).
- `GpsTracker`: per-ambulance tracker. Stores last N updates (configurable).
- Staleness: if latest update is older than `gps_stale_threshold_s`, marks GPS as STALE.
- Route deviation: compares current position against planned route;
  flags deviation if position is outside a configurable corridor.
- SUMO integration (Phase 3): receives position from TraCI vehicle queries.

**`emergency_request.py`**
- `EmergencyRequest`: extends/wraps `AmbulanceRequest` with dispatch context.
- Additional fields: `verification_level`, `verification_method`, `gps_source`,
  `junction_etas` (dict of junction_id → predicted ETA seconds),
  `dynamic_reroute_count`, `notification_log`.
- `junction_etas` is populated by the corridor scheduler and updated on each GPS tick.

**`temp_verification.py`**
- `TempVerificationRequest`: holds identity, GPS, hospital, method, token.
- `TempVerifier`: evaluates a submission, assigns `VerificationLevel`, issues a time-limited token.
- Simulated methods in POC:
  - `DISPATCH_OPERATOR`: accepts a mock operator-approval string.
  - `AMBULANCE_APP`: validates a structured JSON payload against required fields.
  - `LICENSE_PLATE`: does a mock lookup in a configurable secondary dict.
- Logs every attempt (success and failure) with reason.

**`verification_state.py`**
```python
class VerificationLevel(Enum):
    UNDETECTED = auto()
    DETECTED   = auto()   # siren confirmed; identity unknown
    VERIFIED   = auto()   # identity confirmed; safety check pending
    AUTHORIZED = auto()   # safety controller approved; priority active

@dataclass
class VerificationRecord:
    ambulance_id: str          # LifeLane ID or temp ID
    is_registered: bool
    verification_level: VerificationLevel
    verification_method: str   # "REGISTERED_DEVICE" | "DISPATCH_OPERATOR" | etc.
    verification_confidence: str  # "HIGH" | "MEDIUM" | "LOW"
    verified_at: Optional[float]
    expires_at: Optional[float]
    approach: Optional[str]
    junction_id: Optional[str]
```

**`session_manager.py`**
- Issues time-limited session tokens for registered ambulances after authentication.
- Prevents duplicate active sessions for the same ambulance.
- Sessions expire automatically; stale sessions are cleaned up on each tick.

**`notifier.py`**
- `Notification`: dataclass with `ambulance_id`, `event_type`, `message`, `timestamp`.
- Event types: `REQUEST_ACCEPTED`, `AUTH_FAILURE`, `ROUTE_CHANGED`, `JUNCTION_PREPARING`,
  `JUNCTION_SERVED`, `HOSPITAL_ARRIVAL`, `VERIFICATION_TIMEOUT`, `UNVERIFIED_SIREN_ALERT`,
  `GPS_STALE`, `REQUEST_EXPIRED`.
- `MockNotifier`: stores notifications in a list; prints to log. No real network calls.
- Future: real ambulance app push notification via API endpoint.

**`dispatch_service.py`**
- `DispatchService`: the orchestration facade.
- Called by the CLI/POC runner and (later) by FastAPI service adapters.
- Does NOT contain safety logic. Safety logic stays in `traffic/signal_controller.py`.
- Flow: receive_detection() → lookup_or_verify() → submit_to_safety_controller() →
  track_gps() → update_junction_etas() → send_notifications().

---

## Hospital Directory (Enhanced from v1)

The mock hospital directory is expanded. Hospital selection is made by the ambulance operator
or dispatch system — never by the siren model.

```python
@dataclass
class Hospital:
    hospital_id: str
    name: str
    node: str                      # Junction/node nearest the hospital
    address: str                   # Descriptive; simulation only
    capabilities: List[str]        # e.g. ["trauma", "cardiac", "pediatric"]
    available: bool                # Simulated availability
    capacity_pct: float            # 0.0–1.0 simulated occupancy
    location: Tuple[float, float]  # (lat, lon) — simulated coordinates
```

Rules:
- The operator selects the hospital. The system does not override this selection.
- If selected hospital is unavailable, the system notifies the operator; it does NOT
  automatically redirect to another hospital.
- The route planner uses the hospital's `node` as the destination.

---

## GPS Tracking Requirements

GPS is **simulated** in the POC (SUMO vehicle positions via TraCI in Phase 3;
mock position objects in Phases 1–2).

Requirements:
- Accept periodic GPS updates with timestamp, position, speed, and heading.
- Detect stale GPS (configurable threshold, default 10 s).
- Detect route deviation (ambulance outside planned route corridor).
- On stale GPS: log, notify operator, use last known position with a staleness flag.
  Do NOT silently continue as if GPS is fresh.
- On route deviation: trigger dynamic reroute calculation; notify operator.
  Cancel or update corridor preparation requests for affected junctions.
- All GPS sources must be labeled: DEVICE (registered), MANUAL (unregistered app), SIMULATED (SUMO).

---

## Junction-wise ETA Requirements

The ETA model must predict arrival time at **every upcoming junction** on the route,
not just the immediate next one. This enables corridor preparation to begin for
junctions further ahead on long routes.

```
junction_etas = {
    "J1": 12.5,    # seconds to J1 stop line (current junction)
    "J2": 41.3,    # seconds to J2 stop line
    "J4": 68.7,    # seconds to J4 stop line
}
```

- ETAs are recalculated on each GPS update tick.
- For Phase 2 (mock): naive ETA = distance_to_junction / current_speed (handle zero speed).
- For Phase 5: XGBoost model predicts per-junction ETA with traffic features.
- Corridor scheduler uses junction ETAs to decide when to issue preparation requests.
- All junction ETAs are logged in the structured event log.

---

## Dynamic Route Updates

When GPS indicates route deviation or a road is closed mid-journey:
1. Route planner recalculates the route from the current GPS position.
2. New junction ETA sequence is computed.
3. Corridor preparation requests for junctions no longer on the route are CANCELLED safely.
4. New preparation requests are issued for the updated route.
5. Operator is notified of the reroute.
6. `dynamic_reroute_count` is incremented on the emergency request.
7. Safety controller for each affected junction is reset to NORMAL via `expire_and_reset()`.

**The selected hospital does NOT change during dynamic reroutes unless the operator explicitly changes it.**

---

## Duplicate Request Prevention

- One active emergency request per ambulance at any time.
- If a second request is submitted while one is active: reject with reason "duplicate_active_request".
- If the same registration number appears from two simultaneous sources: treat as CONFLICT; log; do not grant either automatically.

---

## Failure Handling Requirements

| Failure | Detection | Response |
|---------|-----------|----------|
| Stale GPS | Latest update > `gps_stale_threshold_s` | Mark STALE; notify operator; use last known position with flag; do not treat as fresh |
| Expired request | `now > expiry_at` | `expire_and_reset()` on safety controller; log; notify operator |
| Network/communication failure | Exception or timeout in dispatch service | Log fault; expire active requests; return all affected junctions to NORMAL |
| Route deviation | Position outside route corridor | Trigger reroute; notify operator; cancel stale preparation requests |
| GPS unavailable (unregistered) | No GPS provided in temp verification | Accept manual location entry if provided; log as `GPS_MANUAL`; require higher-confidence verification method |
| Missing destination | No hospital_id in request | Reject request with clear error; do not proceed |
| Invalid identity | Auth failure or unrecognized registration | Log; offer temp pathway; do not advance to VERIFIED |
| Duplicate active request | Second request from same ambulance | Reject with `DUPLICATE_REQUEST` reason; log |
| False siren (DETECTED, no verification) | Verification timeout exceeded | Reset to UNDETECTED; log as `UNVERIFIED_SIREN_EVENT`; notify operator |
| Conflicting approaches | Two approaches simultaneously DETECTED | `CONFLICT`; hold both; do not grant either; alert operator |

---

## Notifications (POC — Simulated)

All notifications are mock (log-based) in the POC. The `notifier.py` module stores them
in memory and writes to the structured event log. A real push-notification channel
(via the ambulance app or a WebSocket/SSE endpoint) would be added in Phase 8/10.

Notification events the system must generate:
- `REQUEST_ACCEPTED`: Ambulance request accepted; route confirmed; ETAs computed.
- `AUTH_FAILURE`: Authentication failed; reason included.
- `VERIFICATION_TIMEOUT`: Siren detected but verification timed out; approach cleared.
- `UNVERIFIED_SIREN_ALERT`: Siren detected on approach but ambulance unverified (operator alert).
- `ROUTE_CHANGED`: Dynamic reroute triggered; new route included.
- `JUNCTION_PREPARING`: Corridor preparation issued for a junction; ETA included.
- `JUNCTION_SERVED`: Ambulance passed through junction; next junction ETA included.
- `GPS_STALE`: GPS updates have stopped; last known position included.
- `REQUEST_EXPIRED`: Request timed out before passage; reason included.
- `HOSPITAL_ARRIVAL`: Ambulance reached hospital node; passage confirmed.

---

## Updated Safety Controller Integration

The safety controller (already built in Phase 1) is NOT modified.
Its state machine (NORMAL → SUSPECTED → CONFIRMED → PREPARING → SERVING → EXITING → RECOVERING) remains.

The new dispatch module sits **outside** the safety controller and feeds verified,
authorized requests into it. The mapping is:

```
VerificationLevel.DETECTED    →  safety controller SUSPECTED / CONFIRMED (audio gate)
VerificationLevel.VERIFIED    →  eligibility for safety controller PREPARING gate
VerificationLevel.AUTHORIZED  →  safety controller PREPARING → SERVING (transition granted)
```

The dispatch module never calls `execute_safe_transition_to_green()` directly.
Only the safety controller calls that method on itself, after all conditions are met.

---

## Updated POC Scenarios for `run-poc`

In addition to the 6 original scenarios (preserved unchanged), the POC must demonstrate:

**Scenario 7 — Registered ambulance: full dispatch workflow (mock)**
- Ambulance authenticates with device credential.
- GPS updates received (mock positions).
- Hospital selected; route planned; junction ETAs computed.
- Corridor preparation triggered; priority granted; passage; recovery.

**Scenario 8 — Unregistered ambulance: dispatch-operator temp verification**
- Siren DETECTED; ambulance not in registry.
- Dispatch operator submits mock approval.
- VERIFIED at HIGH confidence; enters normal workflow.
- Priority granted through same safety checks.

**Scenario 9 — Unregistered ambulance: verification timeout → safe fallback**
- Siren DETECTED; no verification received within timeout.
- System does NOT grant priority.
- Logged as UNVERIFIED_SIREN_EVENT; operator notified; approach cleared.

**Scenario 10 — GPS staleness mid-journey**
- Ambulance active; GPS stops updating.
- System marks GPS STALE; notifies operator; continues with last known position (flagged).
- If staleness exceeds hard limit: request expires safely.

**Scenario 11 — Dynamic reroute**
- Ambulance deviates from planned route.
- System cancels preparation for skipped junctions; recalculates route; reissues preparation.

**Scenario 12 — Duplicate request rejected**
- Second emergency request submitted while one is active.
- Rejected with `DUPLICATE_REQUEST`; existing request unaffected.

**Note:** All new scenarios use mock/simulated data. No real GPS, no real dispatch system.

---

## Updated Repository Layout

```text
d:\LIFELANE\
├── README.md
├── requirements.txt
├── .gitignore
├── pytest.ini
├── config/
│   └── settings.yaml                        # All tuneable parameters (extended)
├── data/
│   ├── raw/UrbanSound8K/                    # User downloads; never commit
│   ├── processed/                           # Generated; never commit
│   └── sumo_logs/                          # Generated; never commit
├── models/                                  # Generated; never commit
├── reports/
├── scripts/
│   ├── download_instructions.md
│   ├── build_audio_features.py              # Phase 4
│   ├── train_siren_classifier.py            # Phase 4
│   ├── generate_sumo_eta_dataset.py         # Phase 5
│   ├── train_eta_model.py                   # Phase 5
│   ├── train_queue_model.py                 # Phase 5
│   ├── run_experiment.py                    # Phase 6
│   └── evaluate_models.py                   # Phase 6
├── src/lifelane_engine/                     # Framework- and database-independent core
│   ├── __init__.py
│   ├── config.py
│   ├── main.py                              # CLI entry point
│   ├── audio/
│   │   ├── __init__.py
│   │   ├── approach_selector.py             # ✅ Built (Phase 1)
│   │   ├── preprocess.py                    # Phase 4 stub
│   │   ├── feature_extractor.py             # Phase 4 stub
│   │   └── siren_classifier.py              # Phase 4 stub
│   ├── ambulance/
│   │   ├── __init__.py
│   │   ├── request.py                       # ✅ Built (Phase 1) — AmbulanceRequest
│   │   └── route_planner.py                 # ✅ Built (Phase 1) — Dijkstra + mock grid
│   ├── dispatch/                            # NEW — Phase 2
│   │   ├── __init__.py
│   │   ├── registry.py                      # Ambulance Registry
│   │   ├── authenticator.py                 # Credential verification
│   │   ├── gps_tracker.py                   # GPS updates + staleness
│   │   ├── emergency_request.py             # Extended request with dispatch context
│   │   ├── temp_verification.py             # Unregistered ambulance pathway
│   │   ├── verification_state.py            # VerificationLevel + VerificationRecord
│   │   ├── session_manager.py               # Session tokens for registered ambulances
│   │   ├── notifier.py                      # Mock operator notifications
│   │   └── dispatch_service.py              # Orchestration facade
│   ├── prediction/
│   │   ├── __init__.py
│   │   ├── eta_model.py                     # Phase 5 stub (naive fallback in Phase 2)
│   │   ├── queue_model.py                   # Phase 5 stub
│   │   └── dataset_builder.py               # Phase 5 stub
│   ├── traffic/
│   │   ├── __init__.py
│   │   ├── signal_controller.py             # ✅ Built (Phase 1) — safety state machine
│   │   ├── corridor_scheduler.py            # ✅ Built (Phase 1) — preparation requests
│   │   └── recovery.py                      # ✅ Built (Phase 1) — bounded recovery
│   ├── simulation/
│   │   ├── __init__.py
│   │   ├── sumo_runner.py                   # Phase 3 stub
│   │   ├── metrics.py                       # ✅ Built (Phase 1)
│   │   └── scenario.py                      # ✅ Built (Phase 1)
│   └── poc/
│       ├── __init__.py
│       └── mock_poc.py                      # ✅ Built (Phase 1) — 6 scenarios; expand to 12
├── sumo/
│   ├── network/                             # Phase 3
│   │   ├── grid.net.xml
│   │   ├── grid.rou.xml
│   │   ├── grid.add.xml
│   │   └── grid.sumocfg
│   └── README.md
├── api/                                     # Phase 8: FastAPI application
│   ├── app/
│   │   ├── main.py
│   │   ├── routers/
│   │   │   ├── simulation.py
│   │   │   ├── ambulances.py                # Registration, auth, GPS, dispatch
│   │   │   ├── emergency_requests.py        # Registered + unregistered pathways
│   │   │   └── hospitals.py
│   │   ├── schemas/
│   │   ├── services/
│   │   └── dependencies.py
│   └── tests/
├── frontend/                                # Phase 9: React + Vite (JavaScript)
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/
│   │   └── hooks/
│   └── package.json
├── migrations/                              # Phase 7: Alembic
└── tests/                                  # Core engine tests
    ├── conftest.py                          # ✅ Built (Phase 1)
    ├── test_approach_selector.py            # ✅ Built (Phase 1) — 18 tests
    ├── test_signal_controller.py            # ✅ Built (Phase 1) — 16 tests
    ├── test_route_planner.py                # ✅ Built (Phase 1) — 9 tests
    ├── test_recovery.py                     # ✅ Built (Phase 1) — 7 tests
    ├── test_config.py                       # ✅ Built (Phase 1) — 6 tests
    ├── test_mock_poc.py                     # ✅ Built (Phase 1) — 3 tests
    ├── test_registry.py                     # Phase 2
    ├── test_authenticator.py                # Phase 2
    ├── test_gps_tracker.py                  # Phase 2
    ├── test_temp_verification.py            # Phase 2
    ├── test_verification_state.py           # Phase 2
    ├── test_dispatch_service.py             # Phase 2
    ├── test_audio_preprocess.py             # Phase 4
    └── test_eta_model.py                    # Phase 5
```

---

## Updated Configuration (settings.yaml additions)

```yaml
# --- Dispatch module ---
dispatch:
  gps_stale_threshold_s: 10.0
  gps_max_history: 50
  route_deviation_corridor_m: 30.0      # metres off planned route before flagging
  temp_verification_timeout_s: 60.0     # seconds to wait for unregistered verification
  temp_verification_expiry_s: 180.0     # shorter expiry for temp-verified requests
  registered_request_expiry_s: 300.0   # standard registered expiry (matches v1)
  max_active_requests_per_ambulance: 1  # prevent duplicates
  session_ttl_s: 3600.0                 # registered ambulance session lifetime
  
# --- Hospital directory ---
hospitals:
  default_availability_check: true
  notify_on_unavailable: true

# --- Verification ---
verification:
  detection_hold_timeout_s: 60.0        # how long to hold DETECTED state waiting for verification
  low_confidence_expiry_reduction: 0.4  # multiply expiry by this for LOW confidence temp verifications
```

---

## Updated PostgreSQL Schema (Phase 7)

All v1 tables are preserved. New tables added:

### New Tables

**`ambulance_registry`**
```sql
ambulance_id        UUID PRIMARY KEY
lifelane_id         TEXT UNIQUE NOT NULL
registration_number TEXT NOT NULL
service_name        TEXT NOT NULL
device_id           TEXT UNIQUE NOT NULL
credential_hash     TEXT NOT NULL           -- never store plaintext
registration_status TEXT NOT NULL           -- ACTIVE / SUSPENDED / REVOKED
registered_at       TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
notes               TEXT
```

**`ambulance_sessions`**
```sql
session_id      UUID PRIMARY KEY
ambulance_id    UUID REFERENCES ambulance_registry(ambulance_id)
session_token   TEXT UNIQUE NOT NULL
created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
expires_at      TIMESTAMPTZ NOT NULL
invalidated_at  TIMESTAMPTZ               -- null if still active
invalidation_reason TEXT
```

**`gps_updates`**
```sql
gps_update_id   UUID PRIMARY KEY
ambulance_id    TEXT NOT NULL              -- lifelane_id or temp_id
request_id      UUID REFERENCES emergency_requests(request_id)
latitude        DOUBLE PRECISION NOT NULL
longitude       DOUBLE PRECISION NOT NULL
speed_ms        DOUBLE PRECISION
heading_deg     DOUBLE PRECISION
gps_source      TEXT NOT NULL              -- DEVICE / MANUAL / SIMULATED
is_stale        BOOLEAN NOT NULL DEFAULT FALSE
recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now()
```

**`emergency_requests`** (replaces/extends v1 `ambulance_requests`)
```sql
request_id              UUID PRIMARY KEY
ambulance_id            TEXT NOT NULL      -- lifelane_id or temp_id
is_registered           BOOLEAN NOT NULL
run_id                  UUID REFERENCES simulation_runs(run_id)
origin_edge             TEXT NOT NULL
destination_edge        TEXT NOT NULL
hospital_id             TEXT NOT NULL
approach                TEXT NOT NULL
junction_id             TEXT NOT NULL
route                   JSONB NOT NULL     -- ordered edge list
emergency_mode          TEXT NOT NULL
verification_level      TEXT NOT NULL      -- DETECTED / VERIFIED / AUTHORIZED
verification_method     TEXT               -- REGISTERED_DEVICE / DISPATCH_OPERATOR / etc.
verification_confidence TEXT               -- HIGH / MEDIUM / LOW
dynamic_reroute_count   INTEGER NOT NULL DEFAULT 0
created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
expiry_at               TIMESTAMPTZ NOT NULL
authorized_at           TIMESTAMPTZ
completed_at            TIMESTAMPTZ
status                  TEXT NOT NULL      -- lifecycle status
```

**`temp_verification_logs`**
```sql
temp_verification_id    UUID PRIMARY KEY
temp_id                 TEXT NOT NULL      -- temporary ambulance ID
announced_registration  TEXT
verification_method     TEXT NOT NULL
verifying_operator_id   TEXT
gps_latitude            DOUBLE PRECISION
gps_longitude           DOUBLE PRECISION
hospital_id             TEXT
verification_confidence TEXT
success                 BOOLEAN NOT NULL
failure_reason          TEXT
verified_at             TIMESTAMPTZ
expires_at              TIMESTAMPTZ
run_id                  UUID REFERENCES simulation_runs(run_id)
```

**`notification_logs`**
```sql
notification_id UUID PRIMARY KEY
ambulance_id    TEXT NOT NULL
request_id      UUID
event_type      TEXT NOT NULL
message         TEXT NOT NULL
delivered       BOOLEAN NOT NULL DEFAULT FALSE
created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
```

**`junction_eta_logs`**
```sql
eta_log_id      UUID PRIMARY KEY
request_id      UUID REFERENCES emergency_requests(request_id)
junction_id     TEXT NOT NULL
predicted_eta_s DOUBLE PRECISION NOT NULL
actual_eta_s    DOUBLE PRECISION           -- filled after passage
gps_source      TEXT NOT NULL
model_version   TEXT
logged_at       TIMESTAMPTZ NOT NULL DEFAULT now()
```

### Indexes
```sql
CREATE INDEX ON emergency_requests (ambulance_id, status);
CREATE INDEX ON emergency_requests (run_id, created_at);
CREATE INDEX ON gps_updates (ambulance_id, recorded_at DESC);
CREATE INDEX ON junction_eta_logs (request_id, junction_id);
CREATE INDEX ON notification_logs (ambulance_id, event_type, created_at);
CREATE INDEX ON temp_verification_logs (temp_id, verified_at);
```

---

## Updated FastAPI Endpoints (Phase 8)

All v1 endpoints preserved. New endpoints:

### Ambulance Registration and Auth
```
POST   /ambulances/register           Register a new ambulance (admin)
GET    /ambulances/{lifelane_id}      Get ambulance details
PATCH  /ambulances/{lifelane_id}/status  Suspend or revoke
POST   /ambulances/authenticate       Credential auth → session token
DELETE /ambulances/sessions/{session_id}  Invalidate session
```

### Emergency Requests (Registered)
```
POST   /emergency-requests                Submit registered ambulance request
GET    /emergency-requests/{request_id}   Get request status + ETAs
DELETE /emergency-requests/{request_id}   Cancel active request
```

### Emergency Requests (Unregistered — Temp Verification)
```
POST   /emergency-requests/temp           Submit unregistered ambulance request
POST   /emergency-requests/temp/{temp_id}/verify   Submit verification data
GET    /emergency-requests/temp/{temp_id}           Get temp request status
```

### GPS
```
POST   /ambulances/{lifelane_id}/gps     Submit GPS update (registered)
POST   /emergency-requests/temp/{temp_id}/gps   Submit GPS (unregistered)
GET    /ambulances/{lifelane_id}/gps/latest      Get latest GPS position
```

### Route and ETA
```
GET    /emergency-requests/{request_id}/route     Get planned route
GET    /emergency-requests/{request_id}/eta       Get junction-wise ETAs
GET    /hospitals                                  List hospitals
GET    /hospitals/{hospital_id}                   Get hospital details
```

### Notifications
```
GET    /ambulances/{lifelane_id}/notifications    Get notification history
GET    /emergency-requests/{request_id}/notifications  Request-scoped notifications
```

**Safety constraint on all endpoints:**
API handlers submit validated commands to the engine service layer.
No API handler may directly call `execute_safe_transition_to_green()` or modify signal phases.

---

## Updated React Dashboard Requirements (Phase 9)

The dashboard must display (in addition to v1 requirements):
- Ambulance registry status (registered / unregistered / temp-verified).
- Verification level badge (UNDETECTED / DETECTED / VERIFIED / AUTHORIZED) per ambulance.
- GPS track on the simulated network map.
- Junction-wise ETA table for each active ambulance.
- Notification feed (real-time or polled).
- Temp verification panel showing method, confidence, and expiry.
- "Unverified siren alert" banner when DETECTED but unverified.
- Hospital directory with simulated availability.

All data must be clearly labeled as simulated. The UI may NOT issue signal commands.

---

## Updated Phase Plan

Phases 1, 3–10 retain their v1 scope. Phase 2 is significantly expanded.

### Phase 1 — Scaffold and Dataset-Free Mock POC ✅ COMPLETE
59/59 tests pass. 6 POC scenarios pass. No SUMO, dataset, or model required.

### Phase 2 — Domain Core: Safety + Dispatch + Verification (EXPANDED)

**Original Phase 2 scope (preserved):**
- Typed requests, approach confirmation, authorization/expiry validation.
- Route planner, state machine, conflict checks, safe transitions, bounded recovery.
- Unit tests proving siren alone cannot cause green.
- All domain logic independent of frameworks.

**Added Phase 2 scope (new):**
- `dispatch/` sub-package: all 9 modules listed above.
- Ambulance Registry (in-memory mock).
- Credential authenticator (SHA-256 mock hashing).
- GPS tracker with staleness and deviation detection.
- `VerificationLevel` enum and `VerificationRecord` dataclass.
- Temporary verification pathway (all three mock methods).
- Session manager.
- Mock notifier.
- Dispatch service orchestration facade.
- Extended `EmergencyRequest` with dispatch context.
- Junction-wise ETA calculation (naive distance/speed for Phase 2).
- Dynamic reroute logic (using existing route planner).
- Duplicate request detection.
- All failure handling cases: stale GPS, invalid identity, missing destination, duplicate, etc.
- POC scenarios 7–12 (mock dispatch workflow).
- New test files: `test_registry.py`, `test_authenticator.py`, `test_gps_tracker.py`,
  `test_temp_verification.py`, `test_verification_state.py`, `test_dispatch_service.py`.

**Phase 2 acceptance gate:**
- All existing tests (59) still pass.
- New dispatch tests pass.
- `run-poc` demonstrates all 12 scenarios using mock data.
- Safety invariant: DETECTED alone cannot grant any green.
- Safety invariant: VERIFIED alone cannot grant any green.
- Only AUTHORIZED + safety controller transition grants green.
- No FastAPI, PostgreSQL, React code added.

### Phase 3 — SUMO/TraCI Integration (v1 scope + GPS from TraCI)
- 2×2 network, routes, detectors, signal programs, scenario runner.
- TraCI integration: vehicle positions fed to `GpsTracker` as SIMULATED source.
- Vehicle-based passage detection (unchanged).
- Junction-wise ETA uses actual SUMO distances and speeds.

### Phase 4 — Audio ML (unchanged from v1)
- UrbanSound8K preprocessing, YAMNet embeddings, classifier training.
- Mock audio adapter preserved for dataset-free demo.

### Phase 5 — ETA/Queue Prediction + Corridor Preparation (v1 + junction-wise)
- Multi-seed SUMO datasets; XGBoost ETA; optional queue model.
- Corridor scheduler uses junction-wise ETAs from the dispatch module.
- ETA predictions logged via `junction_eta_logs` structure (mock CSV in Phase 5).

### Phase 6 — Experiments and Core Acceptance (v1 scope)
- Baseline / fixed-formula / naive-ETA / learned-ETA comparisons.
- Registered vs. unregistered ambulance scenarios in experiments.
- Export metrics including verification_confidence breakdown.

### Phase 7 — PostgreSQL Persistence (v1 schema + new tables)
- All v1 tables plus the 6 new tables defined above.
- Repository/adapter layer for dispatch module (currently in-memory).
- Integration tests with and without database.

### Phase 8 — FastAPI Backend (v1 endpoints + new dispatch/GPS/notification endpoints)
- All new endpoints listed above.
- Unregistered ambulance flow tested via API.
- No signal logic in API handlers.

### Phase 9 — React Dashboard (v1 + dispatch/verification UI)
- Verification badges, GPS track, junction ETA table, notification feed.
- Temp verification panel.
- Hospital directory view.

### Phase 10 — Full-Stack Integration (v1 + dispatch integration tests)
- Registered and unregistered ambulance end-to-end flows.
- GPS staleness and reroute scenarios tested across full stack.
- Auth failure and duplicate request tested across full stack.
- Fail-closed: no green on any failure path.

---

## Updated Test Plan

### Existing tests (59, all ✅ passing)
Preserved unchanged. All must continue to pass after any new code is added.

### Phase 2 new tests

**`test_registry.py`**
- Register an ambulance and look it up by device_id.
- Register duplicate device_id → raises error.
- Lookup unknown → returns None.
- Update status ACTIVE → SUSPENDED.
- MockRegistry.build_default() returns expected ambulances.

**`test_authenticator.py`**
- Valid credential → AuthResult(success=True, ambulance_id=...).
- Wrong credential → AuthResult(success=False, reason="invalid_credential").
- SUSPENDED ambulance → AuthResult(success=False, reason="suspended").
- REVOKED ambulance → AuthResult(success=False, reason="revoked").
- Unknown device_id → AuthResult(success=False, reason="not_found").

**`test_gps_tracker.py`**
- Fresh GPS update → not stale.
- GPS update > stale_threshold seconds old → marked STALE.
- Position inside route corridor → no deviation flag.
- Position outside corridor → deviation flagged.
- History limited to max_history entries.
- SUMO source labeled correctly.

**`test_temp_verification.py`**
- DISPATCH_OPERATOR method with valid approval token → VERIFIED, HIGH confidence.
- AMBULANCE_APP method with complete payload → VERIFIED, MEDIUM confidence.
- LICENSE_PLATE method with known registration → VERIFIED, LOW confidence.
- LICENSE_PLATE method with unknown registration → NOT_VERIFIED.
- Missing hospital_id → rejected with clear error.
- Missing GPS + missing manual location → rejected.
- Expired verification token → rejected.
- All attempts logged regardless of outcome.

**`test_verification_state.py`**
- Initial level is UNDETECTED.
- DETECTED cannot advance directly to AUTHORIZED (must pass through VERIFIED).
- VERIFIED cannot advance directly to SERVING (must pass safety controller).
- VerificationRecord fields are complete after each transition.

**`test_dispatch_service.py`**
- Registered flow: authenticate → create request → GPS update → junction ETAs → submit to controller.
- Unregistered flow: detect → temp verify → create request → submit to controller.
- Stale GPS detected → notification generated.
- Route deviation → reroute triggered; old preparation cancelled.
- Duplicate request → rejected with DUPLICATE_REQUEST.
- Expired request → expire_and_reset on controller; notification sent.
- Conflicting approach → CONFLICT held; neither granted.

### Failure-case tests (Phase 2)
- Invalid ambulance identity (unknown device_id) → DETECTED; temp pathway offered; no automatic priority.
- GPS unavailable for unregistered → accepted with MANUAL location; lower confidence.
- Missing destination → request rejected; clear error message.
- Communication failure simulation → requests expired; controllers reset to NORMAL.
- Two simultaneous unregistered ambulances on same approach → CONFLICT; neither verified automatically.
- False siren: DETECTED → verification timeout → UNDETECTED; no green ever granted.

---

## What Can Be Simulated vs. What Requires Real Hardware

| Feature | University Prototype (POC) | Requires Real Hardware/External System |
|---------|---------------------------|--------------------------------------|
| Siren detection (4 channels) | Simulated via mock audio scores + UrbanSound8K classifier | Real microphone arrays + signal processing |
| GPS tracking | SUMO vehicle positions (TraCI) or mock coordinates | Real GPS device in ambulance |
| Registered ambulance authentication | Mock credential hash in in-memory registry | Real PKI certificate or secure token |
| Dispatch operator verification | Mock approval string in POC | Real dispatch center integration |
| Ambulance app submission | Structured data payload in POC | Real mobile app with auth |
| License plate cross-reference | Mock lookup dict in POC | Real DVLA/transport authority API |
| Hospital selection | Operator-provided in mock request | Real hospital management system |
| Hospital availability | Simulated boolean flag | Real hospital capacity system |
| Signal preemption | SUMO + TraCI (simulation only) | Real traffic management system (OUT OF SCOPE) |
| Notifications | Log-based mock notifier | Real push notification service |
| Route planning | Dijkstra on mock graph / SUMO network | Real road network data (OSM etc.) |

**Hard boundary:** Real signal preemption of public-road traffic is ALWAYS out of scope.
This restriction applies regardless of how accurately the dispatch module is implemented.

---

## Design Decisions Requiring Approval

The following questions require a decision before Phase 2 implementation begins.
No implementation will start until you approve or modify these.

### Decision 1: Verification Timeout Duration
**Question:** How long should the system hold the DETECTED state waiting for unregistered ambulance verification before clearing to UNDETECTED?

**Default proposed:** 60 seconds (configurable in settings.yaml).

**Options:**
- A. 60 s (default; configurable)
- B. 30 s (more aggressive clearing)
- C. 120 s (more lenient; risk of longer false-hold)
- D. Unlimited (hold until explicit cancellation — not recommended for safety)

### Decision 2: GPS Unavailable for Unregistered Ambulance
**Question:** If an unregistered ambulance submits a temp verification request but provides no GPS location (GPS unavailable), should the system:

**Options:**
- A. Reject the request entirely (strict; safest; may leave real emergency unassisted)
- B. Accept with manually entered location and lower confidence (proposed default; inclusive)
- C. Accept with zero GPS and flag for operator decision (most permissive; highest operator workload)

### Decision 3: Trust Level and Priority
**Question:** Should registered and temporarily-verified ambulances receive the same level of signal priority, or should registered ambulances get precedence in a conflict?

**Options:**
- A. Equal priority for all verified ambulances regardless of method (simplest; consistent safety rules)
- B. Registered gets precedence over temp-verified if both approach the same junction simultaneously (more complex; reflects real-world trust hierarchy)
- C. Configurable flag per scenario (most flexible; adds test complexity)

### Decision 4: Behavior When Selected Hospital is Unavailable
**Question:** If the operator selects Hospital H1 but the simulation marks it unavailable:

**Options:**
- A. Reject the request with a clear error (operator must re-select)
- B. Accept the request; notify the operator of unavailability; proceed anyway
- C. Accept; suggest alternatives in the notification; let operator decide

### Decision 5: Duplicate Active Request Handling
**Question:** If an ambulance already has an active request and submits a second:

**Options:**
- A. Reject the second request with `DUPLICATE_REQUEST` (proposed default)
- B. Cancel the first and accept the second (supports mid-journey destination change)
- C. Queue the second; activate when first completes

### Decision 6: Temporary Verification Methods in POC
**Question:** Which of the three temp verification methods should be demonstrated in the POC?

**Options:**
- A. All three (DISPATCH_OPERATOR, AMBULANCE_APP, LICENSE_PLATE)
- B. DISPATCH_OPERATOR only (simplest; most credible for educational demo)
- C. DISPATCH_OPERATOR + AMBULANCE_APP (two methods; covers main use cases)

---

## Unchanged Requirements from v1

The following are explicitly preserved without modification:

- Audio ML pipeline (UrbanSound8K, YAMNet, fold IDs, LogisticRegression, thresholding).
- Per-approach selector (3-window confirmation, cooldown, rate limits).
- SUMO 2×2 grid (J1–J4, two ambulance routes, configurable traffic demand).
- XGBoost ETA regression (multi-seed, run-level splits, MAE reporting).
- Optional queue-clearance model.
- Independent safety controller state machine and all safety axioms.
- Bounded recovery (timing + queue recovery tracked separately; no phase-zero reset).
- Experiment comparisons (baseline / fixed-formula / naive-ETA / learned-ETA).
- PostgreSQL + SQLAlchemy 2.x + Alembic (Phase 7).
- FastAPI + Pydantic (Phase 8).
- React + Vite JavaScript (Phase 9).
- Architecture boundary: engine independent of all application layers.
- Required README verbatim wording about UrbanSound8K and SUMO limitations.
- Engineering rules: no fabricated results, no silent library replacement, CPU-only.

---

## Required README Additions (v2)

In addition to the v1 required verbatim wording, add:

> LifeLane supports both registered and unregistered ambulances through a three-tier
> verification model. Siren detection (DETECTED) is supporting evidence only and never
> grants signal priority. Identity verification (VERIFIED) is a prerequisite for
> entering the safety controller workflow. Only a fully AUTHORIZED request, approved
> by the independent safety controller, can initiate a signal-priority transition.
> Temporary verification for unregistered ambulances is simulated in this POC.
> No real dispatch system, GPS device, or vehicle authentication is used.

---

## Engineering Rules (v2 — extends v1)

All v1 rules apply. Additional rules:

- Never store plaintext credentials; use hashed representations even in mock/POC.
- GPS staleness detection must be active at all times when GPS is used.
- Verification state transitions must be logged with timestamp, method, and confidence.
- No verification pathway may bypass the independent safety controller.
- Temporary verification tokens must have an expiry; unlimited tokens are not permitted.
- The dispatch module must have its own unit tests independent of SUMO and audio ML.
- Notification events must be generated for every meaningful state change in the dispatch workflow.
- All design decisions listed above must be answered by the user before Phase 2 implementation.

