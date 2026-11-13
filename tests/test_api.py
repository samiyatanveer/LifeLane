"""API tests for LifeLane backend.

Uses pytest-asyncio (asyncio_mode=auto set in pytest.ini) + httpx ASGI transport.
Runs entirely in-process -- no live server needed.
"""
from __future__ import annotations
import io
import uuid
import wave
import pytest

try:
    from httpx import AsyncClient, ASGITransport
except ImportError:
    pytest.skip("httpx not installed -- run: pip install httpx", allow_module_level=True)


# -- helpers -------------------------------------------------------------------

def _make_wav(duration_ms: int = 200, sample_rate: int = 16000) -> bytes:
    n = int(sample_rate * duration_ms / 1000)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n)
    return buf.getvalue()


# -- fixture -------------------------------------------------------------------

@pytest.fixture()
async def client():
    """In-process ASGI client -- triggers lifespan (DB init + model load)."""
    # Reset simulation singleton between tests so state is clean
    import backend.services.simulation as sim_mod
    sim_mod._service = None

    from backend.app import app
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


# -- health --------------------------------------------------------------------

async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert "inference" in body


async def test_model_info(client):
    r = await client.get("/api/model-info")
    assert r.status_code == 200
    body = r.json()
    assert body["model_type"] in ("REAL", "SYNTHETIC", "MOCK_YAMNET")
    assert isinstance(body["is_synthetic"], bool)


# -- detection -----------------------------------------------------------------

async def test_detect_valid_wav(client):
    wav = _make_wav()
    r = await client.post(
        "/api/detect",
        files={"file": ("test.wav", wav, "audio/wav")},
        data={"junction_id": "J1", "approach": "north"},
    )
    assert r.status_code == 201
    body = r.json()
    assert "is_siren" in body
    assert isinstance(body["confidence"], float)
    assert body["model_type"] in ("REAL", "SYNTHETIC", "MOCK_YAMNET")


async def test_detect_empty_file_rejected(client):
    r = await client.post(
        "/api/detect",
        files={"file": ("empty.wav", b"", "audio/wav")},
    )
    assert r.status_code == 400


async def test_list_detections(client):
    r = await client.get("/api/detections")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# -- dispatch ------------------------------------------------------------------

async def test_register_ambulance(client):
    unique_device = f"DEV-{uuid.uuid4().hex[:8]}"
    r = await client.post("/api/ambulances/register", json={
        "registration_number": "KHI-TEST-01",
        "service_name": "Test EMS",
        "device_id": unique_device,
    })
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "ACTIVE"
    assert body["lifelane_id"].startswith("LL-")


async def test_duplicate_device_rejected(client):
    device_id = f"DEV-DUP-{uuid.uuid4().hex[:6]}"
    payload = {"registration_number": "KHI-DUP", "service_name": "EMS", "device_id": device_id}
    r1 = await client.post("/api/ambulances/register", json=payload)
    assert r1.status_code == 201
    r2 = await client.post("/api/ambulances/register", json=payload)
    assert r2.status_code == 409


async def test_list_ambulances(client):
    r = await client.get("/api/ambulances")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_create_request(client):
    r = await client.post("/api/requests", json={
        "ambulance_id": "LL-TESTAMB",
        "origin_edge": "EDGE-A",
        "destination_edge": "EDGE-B",
        "hospital_id": "HOSP-1",
        "approach": "north",
        "junction_id": "J1",
        "emergency_mode": "EMERGENCY",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "PENDING"
    assert body["request_id"].startswith("REQ-")
    return body["request_id"]


async def test_update_request_status(client):
    # Create first
    r = await client.post("/api/requests", json={
        "ambulance_id": "LL-UPD",
        "origin_edge": "E1",
        "destination_edge": "E2",
        "hospital_id": "H1",
    })
    assert r.status_code == 201
    request_id = r.json()["request_id"]
    # Update
    r2 = await client.patch(f"/api/requests/{request_id}/status", json={"status": "ACTIVE"})
    assert r2.status_code == 200
    assert r2.json()["status"] == "ACTIVE"


# -- signals -------------------------------------------------------------------

async def test_list_signals(client):
    r = await client.get("/api/signals")
    assert r.status_code == 200
    junctions = r.json()
    assert len(junctions) == 4
    for j in junctions:
        assert j["is_simulation"] is True
        assert j["state"] == "NORMAL"


async def test_signal_request_priority(client):
    r = await client.post("/api/signals/J1/simulate", json={
        "action": "request_priority",
        "ambulance_id": "LL-TEST",
        "approach": "north",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "SERVING"
    assert body["is_simulation"] is True


async def test_signal_confirm_passage(client):
    await client.post("/api/signals/J2/simulate", json={"action": "request_priority", "approach": "east"})
    r = await client.post("/api/signals/J2/simulate", json={"action": "confirm_passage"})
    assert r.status_code == 200
    assert r.json()["state"] == "NORMAL"


async def test_signal_cancel(client):
    await client.post("/api/signals/J3/simulate", json={"action": "request_priority", "approach": "west"})
    r = await client.post("/api/signals/J3/simulate", json={"action": "cancel"})
    assert r.status_code == 200
    assert r.json()["state"] == "NORMAL"


async def test_signal_invalid_action(client):
    r = await client.post("/api/signals/J1/simulate", json={"action": "INVALID_ACTION"})
    assert r.status_code == 422


async def test_signal_unknown_junction(client):
    r = await client.post("/api/signals/J99/simulate", json={"action": "reset"})
    assert r.status_code == 422


# -- events & stats ------------------------------------------------------------

async def test_list_events(client):
    r = await client.get("/api/events")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_stats(client):
    r = await client.get("/api/stats")
    assert r.status_code == 200
    body = r.json()
    for key in ("total_detections", "siren_detections", "total_ambulances",
                "total_requests", "pending_requests", "active_junctions", "signal_events"):
        assert key in body, f"Missing key: {key}"
