"""
LifeLane SUMO Demo — Standalone FastAPI Backend v4
Port 8080. Serves the frontend AND streams full vehicle + signal state via WebSocket.
Push interval reduced to 200 ms for smoother rendering.
ML model info + evaluation endpoints added.
"""
import json, asyncio, subprocess, sys
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# ── ML engine (lazy import — server runs even without ML) ─────────────────────
_ML_ENGINE_DIR = Path(__file__).parent / "ml_engine"
if str(_ML_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ML_ENGINE_DIR))
try:
    from model_service import get_model_service
    _ml_svc_server = get_model_service(_ML_ENGINE_DIR / "models")
    _ML_SERVER_OK = True
except Exception as _ml_err:
    _ml_svc_server = None
    _ML_SERVER_OK = False
    print(f"[WARN] ML engine unavailable in server: {_ml_err}")

app = FastAPI(title="LifeLane SUMO Demo", version="4.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

BASE_DIR        = Path(__file__).parent.parent
FRONTEND_DIR    = BASE_DIR / "frontend"
DEMO_HTML       = BASE_DIR / "lifelane_demo.html"   # ← the uploaded single-file demo
SUMO_DIR        = BASE_DIR / "sumo"
STATE_FILE      = SUMO_DIR / "sim_state.json"
CONTROLLER      = SUMO_DIR / "traci_controller.py"
_proc: subprocess.Popen | None = None
_speed_scale: float = 1.0   # future: wire to backend step-delay scaling


def _state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"running": False, "vehicles": [], "error": "not started"}


# ── Serve frontend pages ──────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def root():
    """Main page: serve the LifeLane single-file interactive demo (lifelane_demo.html)."""
    if DEMO_HTML.exists():
        return HTMLResponse(DEMO_HTML.read_text(encoding="utf-8"))
    # Fallback to old SUMO dashboard if demo html missing
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return HTMLResponse(index.read_text(encoding="utf-8"))
    return HTMLResponse("<h2>LifeLane — open <a href='/docs'>/docs</a></h2>")

@app.get("/demo", response_class=HTMLResponse)
async def demo_page():
    """Alias: also serve the demo at /demo."""
    if DEMO_HTML.exists():
        return HTMLResponse(DEMO_HTML.read_text(encoding="utf-8"))
    return HTMLResponse("<h2>lifelane_demo.html not found</h2>")

@app.get("/sim", response_class=HTMLResponse)
async def sim_page():
    """Standalone signal preemption visualiser."""
    page = FRONTEND_DIR / "preemption_sim.html"
    if page.exists():
        return HTMLResponse(page.read_text(encoding="utf-8"))
    return HTMLResponse("<h2>preemption_sim.html not found in frontend/</h2>")


@app.post("/api/sumo/start")
async def start():
    global _proc
    if _proc and _proc.poll() is None:
        raise HTTPException(400, "Already running")
    _proc = subprocess.Popen(
        [sys.executable, str(CONTROLLER)],
        cwd=str(SUMO_DIR),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return {"status": "started", "pid": _proc.pid}


@app.post("/api/sumo/stop")
async def stop():
    global _proc
    if _proc and _proc.poll() is None:
        _proc.terminate()
        _proc.wait(timeout=5)
        return {"status": "stopped"}
    return {"status": "not_running"}


@app.post("/api/sumo/pause")
async def pause():
    """Placeholder — pause/resume not yet wired to TraCI step loop."""
    return {"status": "pause_not_implemented"}


@app.post("/api/sumo/resume")
async def resume():
    return {"status": "resume_not_implemented"}


@app.post("/api/sumo/speed")
async def set_speed(multiplier: float = 1.0):
    global _speed_scale
    _speed_scale = max(0.25, min(4.0, multiplier))
    return {"status": "ok", "speed_scale": _speed_scale}


@app.get("/api/sumo/state")
async def get_state():
    return JSONResponse(_state())


@app.websocket("/api/sumo/ws")
async def ws_stream(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(_state())
            await asyncio.sleep(0.2)   # 200 ms — 5 fps, smooth for 0.5 s SUMO steps
    except (WebSocketDisconnect, Exception):
        pass


@app.get("/api/ml/evaluate")
async def ml_evaluate():
    """
    Return the pre-generated model evaluation report.
    Re-generates it if the report file is not present.
    NOTE: Evaluation uses synthetic data (see report for details).
    """
    report_path = BASE_DIR / "reports" / "model_evaluation.txt"
    if report_path.exists():
        content = report_path.read_text(encoding="utf-8")
        return JSONResponse({"report": content, "source": "cached_file", "path": str(report_path)})
    return JSONResponse({"error": "Evaluation report not found. Run: python scripts/evaluate_models.py"}, status_code=404)


# ── ML Info + Evaluation Endpoints ───────────────────────────────────────────

@app.get("/api/ml/info")
async def ml_info():
    """Return real model metadata from the loaded ML engine."""
    if _ml_svc_server is None:
        return JSONResponse({"error": "ML engine not loaded", "loaded": False}, status_code=503)
    return JSONResponse(_ml_svc_server.info())


@app.post("/api/ml/predict/siren")
async def ml_predict_siren(distance_m: float = 100.0, siren_on: bool = True):
    """
    Run a siren probability prediction.
    Params: distance_m (float) — distance to junction; siren_on (bool) — whether siren is active.
    Returns: {p, latency_ms, source, threshold, tier1_activated}
    """
    if _ml_svc_server is None:
        raise HTTPException(503, "ML engine not loaded")
    # Build a deterministic pseudo-audio frame from (siren_on, distance_m)
    import struct
    frame = struct.pack("!Bd", int(siren_on), float(distance_m)) * 32   # 72 bytes
    result = _ml_svc_server.siren_prob(bytes(frame))
    info   = _ml_svc_server.info()
    result["threshold"] = info["siren_threshold"]
    result["tier1_activated"] = result["p"] >= info["siren_threshold"]
    return JSONResponse(result)


@app.post("/api/ml/predict/eta")
async def ml_predict_eta(
    distance_m: float = 150.0,
    speed_ms: float = 14.0,
    queue: int = 3,
    time_since_green_s: float = 8.0,
    demand: str = "medium",
    route_a: bool = True,
):
    """
    Run an ETA prediction.
    Returns: {eta_s, eta_raw, latency_ms, source}
    """
    if _ml_svc_server is None:
        raise HTTPException(503, "ML engine not loaded")
    demand_enc = {"light": 0, "medium": 1, "heavy": 2}.get(demand, 1)
    features = {
        "distance_to_junction_m": float(distance_m),
        "current_speed_ms": float(speed_ms),
        "queue_length_vehicles": float(queue),
        "time_since_green_s": float(time_since_green_s),
        "demand_level_enc": float(demand_enc),
        "is_route_A": 1.0 if route_a else 0.0,
    }
    result = _ml_svc_server.predict_eta(features)
    return JSONResponse(result)


@app.get("/api/ml/state")
async def ml_state():
    """
    Return current sim_state.json with ML fields highlighted.
    Shows siren_p, t1_active, ml_eta_s, ml_latency_ms, ml_source per junction
    and ml_eta_to_J1_s, ml_eta_to_J2_s in ambulance, plus top-level model_info.
    """
    s = _state()
    ml_snapshot = {
        "model_info": s.get("model_info", {}),
        "junctions": {
            jid: {
                "siren_p":       jdata.get("siren_p"),
                "t1_active":     jdata.get("t1_active"),
                "ml_eta_s":      jdata.get("ml_eta_s"),
                "ml_latency_ms": jdata.get("ml_latency_ms"),
                "ml_source":     jdata.get("ml_source"),
            }
            for jid, jdata in s.get("junctions", {}).items()
        },
        "ambulance": {
            "ml_eta_to_J1_s": s.get("ambulance", {}).get("ml_eta_to_J1_s"),
            "ml_eta_to_J2_s": s.get("ambulance", {}).get("ml_eta_to_J2_s"),
        },
        "sim_running": s.get("running", False),
    }
    return JSONResponse(ml_snapshot)


if __name__ == "__main__":
    import uvicorn
    print("\n  LifeLane SUMO Demo v4 — ML Integration")
    print("  ─────────────────────────────────────────────────")
    print("  🚑 Live Demo        →  http://localhost:8080/")
    print("  🚑 Demo (alias)     →  http://localhost:8080/demo")
    print("  🚦 Preemption Sim   →  http://localhost:8080/sim")
    print("  🤖 ML Model Info    →  http://localhost:8080/api/ml/info")
    print("  📊 ML State         →  http://localhost:8080/api/ml/state")
    print("  📖 API Docs         →  http://localhost:8080/docs")
    print("  Press Ctrl+C to stop.\n")
    uvicorn.run(app, host="0.0.0.0", port=8080)
