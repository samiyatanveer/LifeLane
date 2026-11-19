"""API tests for LifeLane backend.

Uses pytest-asyncio (asyncio_mode=auto set in pytest.ini) + httpx ASGI transport.
Runs entirely in-process -- no live server needed.
"""
from __future__ import annotations
import io
import uuid
import wave
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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
async def client(tmp_path, monkeypatch):
    """In-process ASGI client -- triggers lifespan (DB init + model load)."""
    # Reset simulation singleton between tests so state is clean
    import backend.services.simulation as sim_mod
    sim_mod._service = None

    import backend.database as database
    from backend.app import app
    from backend.models import UserRecord
    from backend.security import hash_password
    test_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'api-test.db'}")
    test_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(database, "AsyncSessionLocal", test_factory)
    await database.init_db()
    async with test_factory() as session:
        session.add(UserRecord(username="dispatcher", password_hash=hash_password("dispatcher-password"), role="DISPATCHER"))
        await session.commit()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    await test_engine.dispose()


async def _headers(client):
    response = await client.post("/api/auth/login", json={"username": "dispatcher", "password": "dispatcher-password"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _registration_payload(plate: str):
    return {"registration_number": plate, "service_name": "Test EMS", "contact_name": "Test Contact", "contact_phone": "+923001234567", "vehicle_type": "Basic Life Support", "password": "test-password-123"}


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
    r = await client.post("/api/ambulances/register", json=_registration_payload(f"KHI-TEST-{uuid.uuid4().hex[:6]}"))
    assert r.status_code == 201
    body = r.json()
    assert body["ambulance"]["status"] == "ACTIVE"
    assert body["lifelane_id"].startswith("LL-")


async def test_duplicate_device_rejected(client):
    payload = _registration_payload("KHI-DUP")
    r1 = await client.post("/api/ambulances/register", json=payload)
    assert r1.status_code == 201
    r2 = await client.post("/api/ambulances/register", json=payload)
    assert r2.status_code == 409


async def test_list_ambulances(client):
    r = await client.get("/api/ambulances", headers=await _headers(client))
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_create_request(client):
    registered = await client.post("/api/ambulances/register", json=_registration_payload("KHI-REQUEST"))
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    r = await client.post("/api/requests", json={
        "origin_edge": "EDGE-A",
        "destination_edge": "EDGE-B",
        "hospital_id": "HOSP-1",
        "approach": "north",
        "junction_id": "J1",
        "emergency_mode": "EMERGENCY",
    }, headers=headers)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "PENDING"
    assert body["request_id"].startswith("REQ-")
    return body["request_id"]


async def test_update_request_status(client):
    registered = await client.post("/api/ambulances/register", json=_registration_payload("KHI-UPD"))
    ambulance_headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    # Create first
    r = await client.post("/api/requests", json={
        "origin_edge": "E1",
        "destination_edge": "E2",
        "hospital_id": "H1",
    }, headers=ambulance_headers)
    assert r.status_code == 201
    request_id = r.json()["request_id"]
    # Update
    r2 = await client.patch(f"/api/requests/{request_id}/status", json={"status": "ACTIVE"}, headers=await _headers(client))
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
    }, headers=await _headers(client))
    assert r.status_code == 403


async def test_signal_confirm_passage(client):
    r = await client.post("/api/signals/J2/simulate", json={"action": "confirm_passage"}, headers=await _headers(client))
    assert r.status_code == 200
    assert r.json()["state"] == "NORMAL"


async def test_signal_cancel(client):
    r = await client.post("/api/signals/J3/simulate", json={"action": "cancel"}, headers=await _headers(client))
    assert r.status_code == 200
    assert r.json()["state"] == "NORMAL"


async def test_signal_invalid_action(client):
    r = await client.post("/api/signals/J1/simulate", json={"action": "INVALID_ACTION"}, headers=await _headers(client))
    assert r.status_code == 422


async def test_signal_unknown_junction(client):
    r = await client.post("/api/signals/J99/simulate", json={"action": "reset"}, headers=await _headers(client))
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
