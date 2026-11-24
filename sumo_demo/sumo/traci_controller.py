#!/usr/bin/env python3
"""
LifeLane SUMO TraCI Controller — v3.1
======================================
Proper one-green-at-a-time signal control built from real getControlledLinks()
data discovered at runtime. Yellow → all-red → green transitions always used.
Ambulance preemption with safe transitions, route-aware distance.
STRICT_ONE_GREEN verified every step.
"""

import os, sys, json, time, subprocess, math
from pathlib import Path
from collections import defaultdict

# ── ML Engine (lazy import — SUMO can run without it) ─────────────────────────
try:
    _ML_ENGINE_DIR = Path(__file__).parent.parent / "backend" / "ml_engine"
    if str(_ML_ENGINE_DIR) not in sys.path:
        sys.path.insert(0, str(_ML_ENGINE_DIR))
    from model_service import get_model_service, SIREN_THRESHOLD
    _ML_OK = True
except Exception as _ml_exc:
    _ML_OK = False
    print(f"[WARN] ML engine not loaded: {_ml_exc} — running in DEMO DATA mode")

# ── SUMO / TraCI discovery ────────────────────────────────────────────────────
SUMO_DIR = Path(__file__).parent
SUMO_HOME_CANDIDATES = [
    r"C:\Users\hp\Desktop\SUMO\sumo-win64-1.28.0",
    r"C:\Program Files (x86)\Eclipse\Sumo",
    os.environ.get("SUMO_HOME", ""),
]

def find_sumo_home():
    for c in SUMO_HOME_CANDIDATES:
        if c and Path(c).exists():
            return c
    raise EnvironmentError("SUMO not found. Set SUMO_HOME or install SUMO.")

SUMO_HOME  = find_sumo_home()
SUMO_TOOLS = str(Path(SUMO_HOME) / "tools")
if SUMO_TOOLS not in sys.path:
    sys.path.insert(0, SUMO_TOOLS)

try:
    import traci
    TRACI_OK = True
except ImportError:
    TRACI_OK = False
    print("[WARN] traci not found. Run: pip install traci sumolib")

# ═══════════════════════════════════════════════════════════════════════════
# CONFIG  — all tunables in ONE place
# ═══════════════════════════════════════════════════════════════════════════
PORT              = 8813
SUMO_CFG          = str(SUMO_DIR / "lifelane.sumocfg")
STATE_FILE        = str(SUMO_DIR / "sim_state.json")
STEP_LENGTH       = 0.5          # seconds per simulation step

AMBULANCE_ID      = "ambulance_1"

# Junctions the ambulance passes through (in order along its route)
CORRIDOR_JUNCTIONS = ["J1", "J2"]   # ambulance route: amb_start→J1→J2→hospital
# Note: J3 is NOT on the ambulance route (confirmed from lifelane.edg.xml)
ALL_JUNCTIONS      = ["J1", "J2", "J3", "J4"]

# Ambulance's incoming edge at each corridor junction
AMB_INCOMING_EDGE = {
    "J1": "e_start_J1",   # ambulance comes from amb_start → J1 on edge e_start_J1
    "J2": "e_J1_J2",      # ambulance comes from J1 → J2 on edge e_J1_J2
}

# Preemption trigger thresholds
PREEMPT_DISTANCE  = 150.0   # metres
PREEMPT_ETA       = 12.0    # seconds

# Signal phase timings
YELLOW_DURATION   = 3.0     # yellow clearance before switching
ALL_RED_DURATION  = 2.0     # all-red gap between phases (must cover junction clear)
CLEAR_BUFFER      = 2.0     # hold green after ambulance clears junction box

# Normal cycle timings (seconds)
NORMAL_GREEN_TIME  = 15.0
NORMAL_YELLOW_TIME = 3.0
NORMAL_ALLRED_TIME = 2.0

# Safety
STRICT_ONE_GREEN   = True    # enforce ≤1 green approach per step; log violations

# Staggered phase offsets (which approach index each junction starts on)
# J1 starts on W→E (ambulance corridor) so it's already green when amb departs.
# J2 starts on cross (S→N) so it will naturally cycle to W→E by the time amb arrives.
PHASE_OFFSETS = {"J1": 3, "J2": 1, "J3": 0, "J4": 0}

# Preferred approach cycle order per junction: W→E, N→S, E→W, S→N (spec requirement).
# Map edge ids to a sort key; lower = earlier in cycle.
# Any edge not listed gets key 99 (goes at the end).
APPROACH_ORDER_KEY = {
    # J1 edges
    "e_start_J1" : 0,   # W→E  (ambulance corridor)
    "e_north_J1" : 1,   # N→S  cross
    "e_J2_J1"    : 2,   # E→W  main
    "e_J4_J1"    : 3,   # S→N  cross
    # J2 edges
    "e_J1_J2"    : 0,   # W→E  (ambulance corridor)
    "e_J3_J2"    : 1,   # S→N  cross
    # J3 edges
    "e_J2_J3"    : 0,   # W→E
    "e_south_J3" : 1,   # N→S
    "e_J4_J3"    : 2,   # S→N
    # J4 edges
    "e_J1_J4"    : 0,
    "e_J3_J4"    : 1,
}

# ═══════════════════════════════════════════════════════════════════════════
# GLOBALS
# ═══════════════════════════════════════════════════════════════════════════
jfsm = {}           # per-junction FSM dict
preempt_log = []
collision_ids_seen = set()
signal_violations  = 0
amb_start_t  = None
amb_min_spd_pct = 100.0
_evlog = []

# ── ML state ──────────────────────────────────────────────────────────────────
_ml_svc = None          # ModelService singleton (init in run())
_siren_window = {}      # per-junction: list of recent probabilities (sliding window)
_SIREN_WINDOW_SIZE = 3  # frames needed for Tier-1
_siren_crossing_t = {}  # per-junction: sim time when T1 first fired


def _get_demand_level(total_vehicles: int) -> int:
    """Map total vehicle count to demand encoding: 0=light, 1=medium, 2=heavy."""
    if total_vehicles < 10:
        return 0
    if total_vehicles < 20:
        return 1
    return 2


def _make_siren_frame(ambulance_active: bool, distance_m: float) -> bytes:
    """
    Synthesise a 0.5-second audio frame as raw bytes.

    When the ambulance is active and within 300 m: high-energy bytes
    (siren-like) with energy inversely proportional to distance.
    Otherwise: low-energy noise bytes.

    The _mock_embed() hash ensures siren frames produce consistent
    model outputs for the same distance value.
    """
    # Build a reproducible seed from ambulance presence + distance bucket
    if ambulance_active and distance_m is not None and distance_m < 300.0:
        # Siren-like frame: high byte values weighted by proximity
        proximity = max(0.0, 1.0 - distance_m / 300.0)
        # Use deterministic high bytes mixed with proximity
        base = int(proximity * 200) + 50   # 50–250
        frame = bytes([min(255, base + (i % 10)) for i in range(64)])
    else:
        # Background noise: low uniform bytes
        frame = bytes([10 + (i % 5) for i in range(64)])
    return frame

state = {
    "running": False, "step": 0, "time_s": 0.0,
    "ambulance": {
        "active": False, "arrived": False,
        "edge": "", "lane": "", "x": 0.0, "y": 0.0,
        "speed_kmh": 0.0, "accel": 0.0,
        "nextJunction": "—", "distToNext": None, "etaToNext": None,
        "distance_to_J1": None, "distance_to_J2": None,
        "eta_to_J1": None, "eta_to_J2": None,
        "sirenOn": False,
        # ML additions
        "ml_eta_to_J1_s": None,     # XGBoost-predicted ETA to J1
        "ml_eta_to_J2_s": None,     # XGBoost-predicted ETA to J2
    },
    "vehicles": [],
    "junctions": {
        j: {
            "signal": "red", "phase": "NORMAL", "preempted": False,
            "phase_id": 0, "wait_s": 0.0, "queue": 0,
            "fsm_state": "NORMAL", "message": "Normal operation",
            "eta_s": None, "distance_m": None, "passed": False,
            # ML additions (siren + ETA model outputs)
            "siren_p": 0.0,              # latest siren probability (0.0–1.0)
            "siren_frames_active": 0,    # consecutive frames with p >= threshold
            "t1_active": False,          # Tier-1: 3 consecutive frames triggered
            "ml_eta_s": None,            # XGBoost-predicted ETA (seconds)
            "ml_latency_ms": 0.0,        # model call latency
            "ml_source": "DEMO DATA",    # "REAL_MODEL" | "FALLBACK" | "DEMO DATA"
        }
        for j in ALL_JUNCTIONS
    },
    "events": [],
    "stats": {
        "total_preemptions": 0,
        "ambulance_travel_time_s": None,
        "vehicles_in_sim": 0,
        "signal_violations": 0,
        "collisions": [],
    },
    # ML model info (populated at startup if models load OK)
    "model_info": {
        "source":   "DEMO DATA",
        "loaded":   False,
        "clf_name": "—",
        "eta_name": "—",
    },
}


def log(msg):
    t = state["time_s"]
    _evlog.append({"time_s": round(t, 1), "msg": msg})
    if len(_evlog) > 80: _evlog.pop(0)
    print(f"[{t:7.2f}s] {msg}")


def flush():
    state["events"] = list(_evlog[-30:])
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════
# APPROACH GROUPING  — built from getControlledLinks, never hard-coded
# ═══════════════════════════════════════════════════════════════════════════

def discover_approaches(jid):
    """
    Returns ordered list of (edge_id, [link_indices]) tuples.
    One entry = one approach (all links from the same incoming edge).
    Order: W→E, N→S, E→W, S→N as defined in APPROACH_ORDER_KEY.
    """
    try:
        links = traci.trafficlight.getControlledLinks(jid)
    except Exception:
        return []
    groups = defaultdict(list)
    for idx, lt in enumerate(links):
        if not lt:
            continue
        from_edge = lt[0][0].rsplit("_", 1)[0]
        groups[from_edge].append(idx)
    # Sort by APPROACH_ORDER_KEY (W→E=0, N→S=1, E→W=2, S→N=3), unknown edges last
    return sorted(groups.items(), key=lambda kv: APPROACH_ORDER_KEY.get(kv[0], 99))


def build_ryg(jid, green_edges, yellow_edges=None):
    """
    Build RYG state string.  'G' for green_edges, 'y' for yellow_edges, 'r' rest.
    """
    yellow_edges = yellow_edges or set()
    try:
        links = traci.trafficlight.getControlledLinks(jid)
    except Exception:
        return None
    chars = []
    for lt in links:
        if not lt:
            chars.append('r')
            continue
        from_edge = lt[0][0].rsplit("_", 1)[0]
        if from_edge in green_edges:
            chars.append('G')
        elif from_edge in yellow_edges:
            chars.append('y')
        else:
            chars.append('r')
    return "".join(chars)


def apply_ryg(jid, ryg, duration=9999.0):
    if ryg is None:
        return
    try:
        traci.trafficlight.setRedYellowGreenState(jid, ryg)
        traci.trafficlight.setPhaseDuration(jid, duration)
    except Exception as e:
        log(f"[ERR] apply_ryg {jid}: {e}")


def set_all_red(jid):
    try:
        n   = len(traci.trafficlight.getControlledLinks(jid))
        apply_ryg(jid, 'r' * n)
    except Exception as e:
        log(f"[ERR] all_red {jid}: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# SIGNAL SAFETY CHECKER
# ═══════════════════════════════════════════════════════════════════════════

def check_signal_safety(jid, t):
    global signal_violations
    if not STRICT_ONE_GREEN:
        return
    try:
        s     = traci.trafficlight.getRedYellowGreenState(jid)
        links = traci.trafficlight.getControlledLinks(jid)
    except Exception:
        return

    edge_chars = defaultdict(set)
    for idx, lt in enumerate(links):
        if not lt or idx >= len(s):
            continue
        from_edge = lt[0][0].rsplit("_", 1)[0]
        edge_chars[from_edge].add(s[idx])

    green_app  = [e for e, cs in edge_chars.items() if 'G' in cs or 'g' in cs]
    yellow_app = [e for e, cs in edge_chars.items() if 'Y' in cs or 'y' in cs]

    violated = False
    reason   = ""
    if len(green_app) > 1:
        violated = True
        reason = f"multiple green: {green_app}"
    if green_app and yellow_app:
        violated = True
        reason += f" | green+yellow: G={green_app} Y={yellow_app}"

    if violated:
        signal_violations += 1
        state["stats"]["signal_violations"] = signal_violations
        print(f"⚠  SIGNAL VIOLATION  {jid}  t={t:.2f}s — {reason}  current='{s}'")


# ═══════════════════════════════════════════════════════════════════════════
# PER-JUNCTION FSM
# FSM states:
#   NORMAL_GREEN   – one approach has green; count down to yellow
#   NORMAL_YELLOW  – that approach is yellow; count down to all-red
#   NORMAL_ALLRED  – all red; count down to give next approach green
#   PREEMPT_YELLOW – cross traffic going yellow before amb preemption
#   PREEMPT_ALLRED – all red waiting for junction to clear
#   PREEMPT_GREEN  – ambulance has green; hold until it passes
#   HOLD           – amb passed; short hold then resume cycle
#   RESUME_YELLOW  – yellow after hold before resuming normal
#   RESUME_ALLRED  – all-red before next normal approach
# ═══════════════════════════════════════════════════════════════════════════

def init_fsm(jid, start_approach_idx=0):
    approaches = discover_approaches(jid)
    try:
        orig_prog = traci.trafficlight.getProgram(jid)
    except Exception:
        orig_prog = "0"

    jfsm[jid] = {
        "state": "NORMAL_GREEN",
        "timer": NORMAL_GREEN_TIME,
        "approach_idx": start_approach_idx % max(len(approaches), 1),
        "approaches": approaches,            # [(edge_id, [link_indices]), ...]
        "orig_prog":  orig_prog,
        "amb_approach": None,                # edge the ambulance comes from
        "green_grant_t": None,
        "passed": False,
    }
    if approaches:
        edge, _ = approaches[start_approach_idx % len(approaches)]
        apply_ryg(jid, build_ryg(jid, {edge}))


def _cur_approach(jid):
    fsm = jfsm[jid]
    idx = fsm["approach_idx"] % len(fsm["approaches"])
    return fsm["approaches"][idx][0]   # edge id


def _next_approach(jid):
    fsm = jfsm[jid]
    nxt = (fsm["approach_idx"] + 1) % len(fsm["approaches"])
    fsm["approach_idx"] = nxt
    return fsm["approaches"][nxt][0]


def step_fsm(jid, dt, t):
    fsm = jfsm[jid]
    js  = state["junctions"][jid]
    fsm["timer"] -= dt

    s = fsm["state"]

    # ── NORMAL CYCLE ──────────────────────────────────────────────────────
    if s == "NORMAL_GREEN":
        js["fsm_state"] = "NORMAL"
        js["message"]   = f"Green — {_cur_approach(jid)}"
        js["preempted"] = False
        if fsm["timer"] <= 0:
            cur = _cur_approach(jid)
            apply_ryg(jid, build_ryg(jid, set(), {cur}))   # yellow
            fsm["state"] = "NORMAL_YELLOW"
            fsm["timer"] = NORMAL_YELLOW_TIME

    elif s == "NORMAL_YELLOW":
        js["fsm_state"] = "NORMAL"
        js["message"]   = "Yellow — clearing…"
        if fsm["timer"] <= 0:
            set_all_red(jid)
            fsm["state"] = "NORMAL_ALLRED"
            fsm["timer"] = NORMAL_ALLRED_TIME

    elif s == "NORMAL_ALLRED":
        js["fsm_state"] = "NORMAL"
        js["message"]   = "All-red clearance…"
        if fsm["timer"] <= 0:
            nxt = _next_approach(jid)
            apply_ryg(jid, build_ryg(jid, {nxt}))
            fsm["state"] = "NORMAL_GREEN"
            fsm["timer"] = NORMAL_GREEN_TIME
            js["message"] = f"Green — {nxt}"

    # ── PREEMPTION PIPELINE ───────────────────────────────────────────────
    elif s == "PREEMPT_YELLOW":
        js["fsm_state"] = "APPROACHING"
        js["message"]   = "⚠ Preemption: yellow clearance…"
        if fsm["timer"] <= 0:
            set_all_red(jid)
            fsm["state"] = "PREEMPT_ALLRED"
            fsm["timer"] = ALL_RED_DURATION

    elif s == "PREEMPT_ALLRED":
        js["fsm_state"] = "PREEMPTING"
        js["message"]   = "⚠ Preemption: all-red…"
        if fsm["timer"] <= 0:
            _do_grant_amb_green(jid, t)

    elif s == "PREEMPT_GREEN":
        js["fsm_state"] = "SERVING"
        js["message"]   = "🟢 AMBULANCE PRIORITY — GREEN"
        js["preempted"] = True
        js["phase"]     = "PREEMPTED"

    # ── POST-AMBULANCE ────────────────────────────────────────────────────
    elif s == "HOLD":
        js["fsm_state"] = "CROSSING"
        js["message"]   = "🟢 Holding — ambulance clearing junction…"
        if fsm["timer"] <= 0:
            # yellow for the amb approach before resuming
            amb_edge = fsm["amb_approach"] or _cur_approach(jid)
            apply_ryg(jid, build_ryg(jid, set(), {amb_edge}))
            fsm["state"] = "RESUME_YELLOW"
            fsm["timer"] = NORMAL_YELLOW_TIME
            js["passed"]    = True
            js["preempted"] = False
            log(f"{jid} — ambulance cleared; resuming normal cycle")

    elif s == "RESUME_YELLOW":
        js["fsm_state"] = "PASSED"
        js["message"]   = "Resuming — yellow…"
        if fsm["timer"] <= 0:
            set_all_red(jid)
            fsm["state"] = "RESUME_ALLRED"
            fsm["timer"] = NORMAL_ALLRED_TIME

    elif s == "RESUME_ALLRED":
        js["fsm_state"] = "PASSED"
        js["message"]   = "Resuming normal cycle…"
        if fsm["timer"] <= 0:
            fsm["amb_approach"] = None
            nxt = _next_approach(jid)
            apply_ryg(jid, build_ryg(jid, {nxt}))
            fsm["state"] = "NORMAL_GREEN"
            fsm["timer"] = NORMAL_GREEN_TIME
            js["phase"]     = "NORMAL"
            js["preempted"] = False
            js["message"]   = "Normal operation"
            log(f"{jid} — normal cycle resumed at approach {nxt}")

    # ── Shared telemetry update ───────────────────────────────────────────
    try:
        raw = traci.trafficlight.getRedYellowGreenState(jid)
        if 'G' in raw or 'g' in raw: js["signal"] = "green"
        elif 'y' in raw:              js["signal"] = "yellow"
        else:                         js["signal"] = "red"
        js["phase_id"] = traci.trafficlight.getPhase(jid)
        js["wait_s"]   = round(traci.trafficlight.getSpentDuration(jid), 1)
    except Exception:
        pass


def _do_grant_amb_green(jid, t):
    fsm = jfsm[jid]
    amb_edge = fsm["amb_approach"]
    if amb_edge:
        ryg = build_ryg(jid, {amb_edge})
    else:
        # fallback all-red
        n   = len(traci.trafficlight.getControlledLinks(jid))
        ryg = 'r' * n
    apply_ryg(jid, ryg)
    fsm["state"]        = "PREEMPT_GREEN"
    fsm["green_grant_t"]= t
    state["junctions"][jid]["message"] = "🟢 AMBULANCE GREEN — Priority Active"
    log(f"PREEMPT {jid} → GREEN for {amb_edge}  ryg={ryg!r}  t={t:.2f}s")


# ═══════════════════════════════════════════════════════════════════════════
# PREEMPTION TRIGGER
# ═══════════════════════════════════════════════════════════════════════════

_preempt_triggered = set()

def trigger_preemption(jid, amb_edge, t):
    if jid in _preempt_triggered:
        return
    _preempt_triggered.add(jid)
    fsm = jfsm[jid]
    fsm["amb_approach"] = amb_edge
    state["stats"]["total_preemptions"] += 1
    s = fsm["state"]

    if s == "NORMAL_GREEN":
        cur = _cur_approach(jid)
        if cur == amb_edge:
            # Ambulance approach already has green — keep it, skip to PREEMPT_GREEN
            fsm["state"]        = "PREEMPT_GREEN"
            fsm["green_grant_t"]= t
            log(f"PREEMPT {jid} — ambulance approach already GREEN")
        else:
            # Need to yellow-out current approach
            apply_ryg(jid, build_ryg(jid, set(), {cur}))
            fsm["state"] = "PREEMPT_YELLOW"
            fsm["timer"] = YELLOW_DURATION
            log(f"PREEMPT {jid} — yellow on {cur}, then green for {amb_edge}")

    elif s == "NORMAL_YELLOW":
        # Already yellow; go to all-red
        set_all_red(jid)
        fsm["state"] = "PREEMPT_ALLRED"
        fsm["timer"] = ALL_RED_DURATION
        log(f"PREEMPT {jid} — intercepted YELLOW, going to all-red")

    elif s in ("NORMAL_ALLRED", "RESUME_ALLRED"):
        # Already all-red — grant green immediately
        _do_grant_amb_green(jid, t)
        log(f"PREEMPT {jid} — intercepted ALL-RED, granting amb green now")

    elif s in ("RESUME_YELLOW",):
        set_all_red(jid)
        fsm["state"] = "PREEMPT_ALLRED"
        fsm["timer"] = ALL_RED_DURATION
        log(f"PREEMPT {jid} — intercepted RESUME_YELLOW, all-red then amb green")

    elif s in ("PREEMPT_YELLOW","PREEMPT_ALLRED","PREEMPT_GREEN","HOLD"):
        pass  # already in preemption pipeline

    state["junctions"][jid]["message"] = "⚠ Preemption triggered — transitioning…"


def ambulance_cleared(jid, t):
    fsm = jfsm[jid]
    if fsm["state"] != "PREEMPT_GREEN":
        return
    fsm["state"] = "HOLD"
    fsm["timer"] = CLEAR_BUFFER
    if fsm["green_grant_t"] is not None:
        lead = t - fsm["green_grant_t"]
        preempt_log.append({"jid": jid, "green_lead_s": round(lead, 2)})
        log(f"{jid} — ambulance passed. Green was held {lead:.1f}s after grant")


# ═══════════════════════════════════════════════════════════════════════════
# DISTANCE / ETA
# ═══════════════════════════════════════════════════════════════════════════

def route_dist(jid, spd):
    """Route-aware distance from ambulance to junction jid stop-line."""
    edge = AMB_INCOMING_EDGE.get(jid)
    if edge:
        try:
            edge_len = traci.lane.getLength(edge + "_0")
            d = traci.vehicle.getDrivingDistance(AMBULANCE_ID, edge, edge_len)
            return max(0.0, d)
        except Exception:
            pass
    # Euclidean fallback
    try:
        ax, ay = traci.vehicle.getPosition(AMBULANCE_ID)
        jx, jy = traci.junction.getPosition(jid)
        return math.sqrt((ax-jx)**2 + (ay-jy)**2)
    except Exception:
        return None


def queue_at(jid):
    try:
        lanes = set(traci.trafficlight.getControlledLanes(jid))
        return sum(traci.lane.getLastStepHaltingNumber(l) for l in lanes)
    except Exception:
        return 0


# ═══════════════════════════════════════════════════════════════════════════
# AMBULANCE VTYPE CONFIG
# ═══════════════════════════════════════════════════════════════════════════

def configure_ambulance():
    try:
        traci.vehicle.setSpeedFactor(AMBULANCE_ID, 1.3)
        traci.vehicle.setParameter(AMBULANCE_ID, "has.bluelight.device", "true")
        # Keep all SUMO safety checks ON (default speedMode=31)
        traci.vehicle.setSpeedMode(AMBULANCE_ID, 31)
        log("Ambulance: emergency attrs applied (bluelight, speedFactor=1.3)")
    except Exception as e:
        log(f"[WARN] ambulance configure: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN LOOP
# ═══════════════════════════════════════════════════════════════════════════

def run():
    global amb_start_t, amb_min_spd_pct

    sumo_exe = Path(SUMO_HOME) / "bin" / "sumo.exe"
    if not sumo_exe.exists():
        sumo_exe = Path(SUMO_HOME) / "bin" / "sumo"

    cmd = [
        str(sumo_exe), "-c", SUMO_CFG,
        "--remote-port", str(PORT), "--no-step-log",
        "--step-length", str(STEP_LENGTH),
        "--collision.action", "warn",
        "--collision.check-junctions", "true",
        "--time-to-impatience", "30",
        "--lanechange.duration", "2",
    ]
    seed = os.environ.get("LIFELANE_SEED")
    if seed:
        cmd += ["--seed", seed]

    print(f"[SUMO] Starting {sumo_exe}")
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            cwd=str(SUMO_DIR))
    time.sleep(2.0)

    traci.init(PORT)
    state["running"] = True
    log(f"Simulation started — step={STEP_LENGTH}s  STRICT_ONE_GREEN={STRICT_ONE_GREEN}")

    # Init FSMs after SUMO is running (so getControlledLinks works)
    for jid in ALL_JUNCTIONS:
        try:
            init_fsm(jid, PHASE_OFFSETS.get(jid, 0))
            log(f"FSM init {jid}: {len(jfsm[jid]['approaches'])} approaches: "
                f"{[e for e,_ in jfsm[jid]['approaches']]}")
        except Exception as e:
            log(f"[WARN] FSM init {jid}: {e}")

    amb_configured    = False
    amb_seen          = {j: False for j in CORRIDOR_JUNCTIONS}   # preemption triggered
    amb_inside        = {j: False for j in CORRIDOR_JUNCTIONS}   # inside junction box
    amb_cleared_set   = {j: False for j in CORRIDOR_JUNCTIONS}   # fully cleared

    # ── Initialise ML service ──────────────────────────────────────────────
    global _ml_svc
    if _ML_OK:
        try:
            _ml_models_dir = Path(__file__).parent.parent / "backend" / "ml_engine" / "models"
            _ml_svc = get_model_service(_ml_models_dir)
            state["model_info"] = _ml_svc.info()
            if _ml_svc.is_loaded:
                log(f"ML engine READY — clf={state['model_info']['clf_name']}  eta={state['model_info']['eta_name']}")
            else:
                log(f"[WARN] ML engine FALLBACK — {state['model_info'].get('error','?')}")
        except Exception as _ml_init_exc:
            log(f"[WARN] ML service init failed: {_ml_init_exc}")
            _ml_svc = None
    else:
        log("[INFO] ML engine not available — running in DEMO DATA mode")

    t = 0.0
    try:
        step = 0
        while traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()
            step += 1
            state["step"]   = step
            state["time_s"] = round(traci.simulation.getTime(), 2)
            t = state["time_s"]
            vids = traci.vehicle.getIDList()
            state["stats"]["vehicles_in_sim"] = len(vids)

            # ── Collision check ────────────────────────────────────────────
            try:
                for c in traci.simulation.getCollisions():
                    cid = str(getattr(c, 'collider', c))
                    if cid not in collision_ids_seen:
                        collision_ids_seen.add(cid)
                        state["stats"]["collisions"].append(cid)
                        log(f"COLLISION: {cid}")
            except Exception:
                pass

            # ── Vehicle positions ──────────────────────────────────────────
            vlist = []
            for vid in vids:
                try:
                    vx, vy  = traci.vehicle.getPosition(vid)
                    vlist.append({
                        "id": vid,
                        "type": traci.vehicle.getTypeID(vid),
                        "x": round(vx,2), "y": round(vy,2),
                        "angle": round(traci.vehicle.getAngle(vid),1),
                        "speed_kmh": round(traci.vehicle.getSpeed(vid)*3.6,1),
                        "edge": traci.vehicle.getRoadID(vid),
                    })
                except Exception:
                    pass
            state["vehicles"] = vlist

            # ── Ambulance tracking ─────────────────────────────────────────
            amb_active = AMBULANCE_ID in vids
            if amb_active:
                if amb_start_t is None:
                    amb_start_t = t
                    log("Ambulance dispatched: START → J1 → J2 → Hospital")

                if not amb_configured:
                    configure_ambulance()
                    amb_configured = True

                try:
                    ax, ay  = traci.vehicle.getPosition(AMBULANCE_ID)
                    spd     = traci.vehicle.getSpeed(AMBULANCE_ID)
                    max_spd = traci.vehicle.getMaxSpeed(AMBULANCE_ID)
                    if max_spd > 0.1:
                        pct = spd / max_spd * 100
                        if pct < amb_min_spd_pct: amb_min_spd_pct = pct

                    # Next junction telemetry & per-corridor junction distance + ETA
                    next_jid = next_dist = next_eta = None
                    for jid_c in CORRIDOR_JUNCTIONS:
                        if not amb_cleared_set.get(jid_c, False):
                            d = route_dist(jid_c, spd)
                            if d is not None and d >= 0:
                                next_jid  = jid_c
                                next_dist = round(d, 1)
                                next_eta  = round(d / max(spd, 0.1), 1) if spd > 0.05 else None
                            break

                    d_j1 = route_dist("J1", spd) if not amb_cleared_set.get("J1", False) else None
                    d_j2 = route_dist("J2", spd) if not amb_cleared_set.get("J2", False) else None
                    eta_j1 = round(d_j1 / max(spd, 0.1), 1) if (d_j1 is not None and spd > 0.05) else None
                    eta_j2 = round(d_j2 / max(spd, 0.1), 1) if (d_j2 is not None and spd > 0.05) else None

                    state["ambulance"].update({
                        "active": True, "arrived": False,
                        "x": round(ax,2), "y": round(ay,2),
                        "speed_kmh": round(spd*3.6,1),
                        "accel":     round(traci.vehicle.getAcceleration(AMBULANCE_ID),2),
                        "edge": traci.vehicle.getRoadID(AMBULANCE_ID),
                        "lane": traci.vehicle.getLaneID(AMBULANCE_ID),
                        "sirenOn": True,
                        "nextJunction": next_jid or "—",
                        "distToNext": next_dist,
                        "etaToNext":  next_eta,
                        "distance_to_J1": round(d_j1, 1) if d_j1 is not None else None,
                        "distance_to_J2": round(d_j2, 1) if d_j2 is not None else None,
                        "eta_to_J1": eta_j1,
                        "eta_to_J2": eta_j2,
                    })

                    if step % 4 == 0:
                        log(f"Ambulance: Next={next_jid or '—'} | Dist={next_dist}m | ETA={next_eta}s | J1: {round(d_j1,1) if d_j1 is not None else 'passed'}m ({eta_j1}s) | J2: {round(d_j2,1) if d_j2 is not None else 'passed'}m ({eta_j2}s)")

                    # Update per-junction ETA (TraCI-based)
                    for jid_c in CORRIDOR_JUNCTIONS:
                        if not amb_cleared_set.get(jid_c, False):
                            d = route_dist(jid_c, spd)
                            js = state["junctions"][jid_c]
                            js["distance_m"] = round(d,1) if d else None
                            js["eta_s"]      = round(d/max(spd,0.1),1) if (d and spd>0.05) else None

                    # ── ML: ETA + Siren for each corridor junction ─────────
                    if _ml_svc is not None:
                        total_veh = state["stats"]["vehicles_in_sim"]
                        demand_enc = _get_demand_level(total_veh)
                        ml_eta_j1 = None
                        ml_eta_j2 = None

                        for jid_c in CORRIDOR_JUNCTIONS:
                            js = state["junctions"][jid_c]
                            if amb_cleared_set.get(jid_c, False):
                                js["ml_source"] = "passed"
                                continue

                            d = route_dist(jid_c, spd)
                            if d is None:
                                continue

                            # ETA prediction
                            try:
                                time_since_green = js.get("wait_s", 0.0) or 0.0
                                q = js.get("queue", 0) or 0
                                eta_feat = {
                                    "distance_to_junction_m": float(d),
                                    "current_speed_ms":       float(spd),
                                    "queue_length_vehicles":  float(q),
                                    "time_since_green_s":     float(time_since_green),
                                    "demand_level_enc":       float(demand_enc),
                                    "is_route_A":             1.0,  # Route A: J1→J2→hospital
                                }
                                eta_res = _ml_svc.predict_eta(eta_feat)
                                js["ml_eta_s"]       = eta_res["eta_s"]
                                js["ml_latency_ms"]  = eta_res["latency_ms"]
                                js["ml_source"]      = eta_res["source"]
                                if jid_c == "J1":
                                    ml_eta_j1 = eta_res["eta_s"]
                                elif jid_c == "J2":
                                    ml_eta_j2 = eta_res["eta_s"]
                            except Exception as _eta_exc:
                                log(f"[WARN] ML ETA {jid_c}: {_eta_exc}")
                                js["ml_source"] = "FALLBACK"

                            # Siren detection
                            try:
                                frame = _make_siren_frame(True, d)
                                siren_res = _ml_svc.siren_prob(frame)
                                p = siren_res["p"]
                                js["siren_p"] = round(p, 4)

                                # Sliding window for Tier-1
                                if jid_c not in _siren_window:
                                    _siren_window[jid_c] = []
                                win = _siren_window[jid_c]
                                win.append(p >= SIREN_THRESHOLD)
                                if len(win) > _SIREN_WINDOW_SIZE:
                                    win.pop(0)

                                was_t1 = js["t1_active"]
                                js["siren_frames_active"] = sum(win)
                                js["t1_active"] = (len(win) == _SIREN_WINDOW_SIZE and all(win))

                                # Log Tier-1 fire event
                                if js["t1_active"] and not was_t1:
                                    ml_eta_v = js.get("ml_eta_s")
                                    eta_str = f"{ml_eta_v:.1f}s" if ml_eta_v is not None else "?"
                                    log(f"{jid_c} SIREN T1 — p={p:.2f} (3/3 frames) ETA {eta_str} [REAL_MODEL]")
                            except Exception as _sir_exc:
                                log(f"[WARN] ML siren {jid_c}: {_sir_exc}")

                        # Store ML ETAs in ambulance state
                        state["ambulance"]["ml_eta_to_J1_s"] = ml_eta_j1
                        state["ambulance"]["ml_eta_to_J2_s"] = ml_eta_j2

                    # Preemption trigger
                    for jid_c in CORRIDOR_JUNCTIONS:
                        if amb_cleared_set.get(jid_c, False):
                            continue
                        d = route_dist(jid_c, spd)
                        if d is None: continue
                        eta = d / max(spd, 0.1) if spd > 0.05 else 9999
                        if (d < PREEMPT_DISTANCE or eta < PREEMPT_ETA) and not amb_seen[jid_c]:
                            amb_seen[jid_c] = True
                            trigger_preemption(jid_c, AMB_INCOMING_EDGE.get(jid_c), t)

                    # Detect ambulance passing through junction box
                    for jid_c in CORRIDOR_JUNCTIONS:
                        if amb_cleared_set.get(jid_c, False): continue
                        try:
                            jx, jy  = traci.junction.getPosition(jid_c)
                            inside  = math.sqrt((ax-jx)**2+(ay-jy)**2) < 25.0
                        except Exception:
                            inside = False

                        was_inside = amb_inside.get(jid_c, False)
                        if inside and not was_inside:
                            amb_inside[jid_c] = True
                            log(f"{jid_c} — ambulance ENTERED junction box")
                        if was_inside and not inside:
                            amb_inside[jid_c]  = False
                            amb_cleared_set[jid_c] = True
                            state["junctions"][jid_c]["passed"] = True
                            ambulance_cleared(jid_c, t)
                            log(f"{jid_c} — ambulance CLEARED at t={t:.2f}s")

                except Exception as e:
                    log(f"[ERR] amb tracking: {e}")

            elif amb_start_t is not None and not state["ambulance"].get("arrived"):
                tt = round(t - amb_start_t, 1)
                state["ambulance"].update({
                    "active": False, "arrived": True, "sirenOn": False,
                    "nextJunction": "—", "distToNext": None, "etaToNext": None,
                })
                state["stats"]["ambulance_travel_time_s"] = tt
                log(f"Ambulance ARRIVED — travel time: {tt}s")

            # ── Junction FSM step + safety check ──────────────────────────
            for jid in ALL_JUNCTIONS:
                if jid in jfsm:
                    step_fsm(jid, STEP_LENGTH, t)
                    check_signal_safety(jid, t)
                state["junctions"][jid]["queue"] = queue_at(jid)

            flush()

    except Exception as e:
        log(f"Simulation ended: {e}")
        import traceback; traceback.print_exc()
    finally:
        try: traci.close()
        except Exception: pass
        state["running"] = False
        flush()
        proc.terminate()
        print("[SUMO] Terminated.")
        _print_report(t)


# ═══════════════════════════════════════════════════════════════════════════
# SAFETY REPORT
# ═══════════════════════════════════════════════════════════════════════════

def _print_report(end_t):
    print("\n" + "="*62)
    print("  LIFELANE SAFETY REPORT")
    print("="*62)
    sv = signal_violations
    clist = state["stats"]["collisions"]
    print(f"  Signal violations (STRICT_ONE_GREEN=True):  {sv}  "
          f"{'✓ PASS' if sv==0 else '✗ FAIL'}")
    print(f"  Collisions detected:                        {len(clist)}  "
          f"{'✓ PASS' if len(clist)==0 else '✗ FAIL'}")
    if clist:
        print(f"    Ids: {', '.join(clist)}")
    print(f"  Ambulance min speed (% of desired):         "
          f"{amb_min_spd_pct:.1f}%  {'✓' if amb_min_spd_pct>=70 else '⚠ LOW'}")
    print()
    print("  Green lead time (time amb was green before it reached stop-line):")
    seen = set()
    for entry in preempt_log:
        jid = entry["jid"]
        if jid not in seen:
            seen.add(jid)
            gl = entry.get("green_lead_s", "?")
            ok = isinstance(gl, float) and gl >= 3.0
            print(f"    {jid}: {gl:.1f}s  {'✓ ≥3s' if ok else '⚠ <3s'}")
    for jid in CORRIDOR_JUNCTIONS:
        if jid not in seen:
            print(f"    {jid}: not reached / no data")
    print()
    print("  Normal cycle resumed after ambulance passed:")
    for jid in CORRIDOR_JUNCTIONS:
        js  = state["junctions"].get(jid, {})
        fsm = jfsm.get(jid, {})
        ok  = fsm.get("state", "") == "NORMAL_GREEN" and js.get("passed", False)
        fsm_st = fsm.get("state","?")
        print(f"    {jid}: {'OK NORMAL' if ok else '(state='+fsm_st+')'}")
    print("="*62 + "\n")


if __name__ == "__main__":
    if not TRACI_OK:
        print("ERROR: Run  pip install traci sumolib  first.")
        sys.exit(1)
    run()
