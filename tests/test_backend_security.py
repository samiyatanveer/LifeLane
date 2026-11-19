"""Backend-only integration coverage for identity, roles, and safe migrations."""
from __future__ import annotations

import shutil
import sqlite3
import hashlib
import secrets
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.security import hash_password, verify_password


def registration_payload(plate: str) -> dict:
    return {
        "registration_number": plate,
        "service_name": "LifeLane Test EMS",
        "contact_name": "Test Dispatcher",
        "contact_phone": "+923001234567",
        "vehicle_type": "Advanced Life Support",
        "password": "a-long-test-password-1",
    }


@pytest.fixture()
async def client(tmp_path, monkeypatch):
    """Serve the API against an empty temporary DB, never lifelane.db."""
    import backend.database as database
    from backend.app import app
    from backend.models import UserRecord

    test_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'api-test.db'}")
    test_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(database, "AsyncSessionLocal", test_factory)
    await database.init_db()
    async with test_factory() as session:
        session.add(UserRecord(username="dispatcher", password_hash=hash_password("dispatcher-password"), role="DISPATCHER"))
        await session.commit()
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test") as api:
        yield api
    await test_engine.dispose()


async def login(client, username: str, password: str) -> str:
    response = await client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


async def register(client, plate: str) -> dict:
    response = await client.post("/api/ambulances/register", json=registration_payload(plate))
    assert response.status_code == 201, response.text
    return response.json()


async def test_registration_issues_unique_public_id_and_login(client):
    first, second = await register(client, "KHI-UNIQUE-01"), await register(client, "KHI-UNIQUE-02")
    assert first["lifelane_id"].startswith("LL-") and len(first["lifelane_id"]) == 11
    assert first["lifelane_id"] != second["lifelane_id"]
    assert first["ambulance"]["id"] != first["lifelane_id"]
    token = await login(client, first["lifelane_id"], registration_payload("unused")["password"])
    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["ambulance"]["lifelane_id"] == first["lifelane_id"]


async def test_duplicate_registration_and_failed_transaction_roll_back(client):
    await register(client, "KHI-DUP-01")
    duplicate = await client.post("/api/ambulances/register", json=registration_payload("KHI-DUP-01"))
    assert duplicate.status_code == 409
    with patch("backend.routers.dispatch.create_token", new=AsyncMock(side_effect=RuntimeError("forced failure"))):
        failed = await client.post("/api/ambulances/register", json=registration_payload("KHI-ROLLBACK-01"))
    assert failed.status_code == 500
    dispatcher = await login(client, "dispatcher", "dispatcher-password")
    ambulances = await client.get("/api/ambulances", headers={"Authorization": f"Bearer {dispatcher}"})
    assert ambulances.status_code == 200
    assert {row["registration_number"] for row in ambulances.json()} == {"KHI-DUP-01"}


async def test_registration_normalizes_duplicates_and_validates_input(client):
    first = await client.post("/api/ambulances/register", json=registration_payload(" lea-1234 "))
    assert first.status_code == 201
    duplicate = await client.post("/api/ambulances/register", json=registration_payload("LEA-1234"))
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "This vehicle is already registered with LifeLane. If this is your ambulance, please log in using your existing account or contact LifeLane management."
    invalid = registration_payload("not a plate")
    invalid["password"] = "weakpass"
    invalid["contact_phone"] = "phone"
    response = await client.post("/api/ambulances/register", json=invalid)
    assert response.status_code == 422


async def test_login_generic_failure_and_inactive_account(client):
    unknown = await client.post("/api/auth/login", json={"username": "missing", "password": "wrong-password"})
    wrong = await client.post("/api/auth/login", json={"username": "dispatcher", "password": "wrong-password"})
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["detail"] == wrong.json()["detail"] == "Incorrect username or password"
    from backend.database import AsyncSessionLocal
    from backend.models import UserRecord
    async with AsyncSessionLocal() as session:
        session.add(UserRecord(username="inactive", password_hash=hash_password("inactive-password"), role="DISPATCHER", is_active=False))
        await session.commit()
    inactive = await client.post("/api/auth/login", json={"username": "inactive", "password": "inactive-password"})
    assert inactive.status_code == 403


async def test_recovery_is_generic_and_reset_is_single_use_and_revokes_sessions(client):
    from backend.database import AsyncSessionLocal
    from backend.models import PasswordResetTokenRecord, UserRecord
    account = UserRecord(username="reset-staff", password_hash=hash_password("old-password-1"), role="DISPATCHER")
    async with AsyncSessionLocal() as session:
        session.add(account)
        await session.commit()
        await session.refresh(account)
        token = secrets.token_urlsafe(32)
        session.add(PasswordResetTokenRecord(user_id=account.id, token_hash=hashlib.sha256(token.encode()).hexdigest(), expires_at=datetime.now(timezone.utc) + timedelta(minutes=30)))
        await session.commit()
    unknown = await client.post("/api/auth/forgot-password", json={"username": "does-not-exist"})
    known = await client.post("/api/auth/forgot-password", json={"username": "reset-staff"})
    assert unknown.status_code == known.status_code == 200 and unknown.json() == known.json()
    active_token = await login(client, "reset-staff", "old-password-1")
    reset = await client.post("/api/auth/reset-password", json={"token": token, "password": "new-password-2"})
    assert reset.status_code == 200
    assert (await client.get("/api/auth/me", headers={"Authorization": f"Bearer {active_token}"})).status_code == 401
    assert (await client.post("/api/auth/reset-password", json={"token": token, "password": "new-password-3"})).status_code == 400
    assert (await client.post("/api/auth/reset-password", json={"token": "x" * 32, "password": "new-password-3"})).status_code == 400
    assert await login(client, "reset-staff", "new-password-2")


async def test_recovery_rate_limit(client):
    responses = [await client.post("/api/auth/forgot-password", json={"username": "rate-limit-user"}) for _ in range(6)]
    assert [response.status_code for response in responses[:-1]] == [200] * 5
    assert responses[-1].status_code == 429


async def test_roles_revocation_and_cross_ambulance_denial(client):
    first, second = await register(client, "KHI-A-01"), await register(client, "KHI-B-01")
    no_token = await client.get("/api/ambulances")
    assert no_token.status_code == 401
    first_token = first["access_token"]
    forbidden_list = await client.get("/api/ambulances", headers={"Authorization": f"Bearer {first_token}"})
    assert forbidden_list.status_code == 403
    request_payload = {
        "ambulance_id": second["lifelane_id"], "origin_edge": "A", "destination_edge": "B",
        "hospital_id": "H1", "approach": "north", "junction_id": "J1",
    }
    conflict = await client.post("/api/requests", json=request_payload, headers={"Authorization": f"Bearer {first_token}"})
    assert conflict.status_code == 403
    request_payload.pop("ambulance_id")
    own = await client.post("/api/requests", json=request_payload, headers={"Authorization": f"Bearer {first_token}"})
    assert own.status_code == 201 and own.json()["ambulance_id"] == first["lifelane_id"]
    second_requests = await client.get("/api/requests", headers={"Authorization": f"Bearer {second['access_token']}"})
    assert second_requests.status_code == 200 and second_requests.json() == []
    logged_out = await client.post("/api/auth/logout", headers={"Authorization": f"Bearer {first_token}"})
    assert logged_out.status_code == 204
    revoked = await client.get("/api/requests", headers={"Authorization": f"Bearer {first_token}"})
    assert revoked.status_code == 401


async def test_temporary_verification_requires_confirmation_before_priority(client):
    dispatcher = await login(client, "dispatcher", "dispatcher-password")
    headers = {"Authorization": f"Bearer {dispatcher}"}
    started = await client.post("/api/temporary-verifications", json={"contact_phone": "+923009999999", "vehicle_registration": "TMP-PLATE"})
    assert started.status_code == 201
    temporary = started.json()
    payload = {"ambulance_id": temporary["temporary_id"], "origin_edge": "A", "destination_edge": "B", "hospital_id": "H1"}
    unverified = await client.post("/api/requests", json=payload, headers=headers)
    assert unverified.status_code == 403
    confirmed = await client.post("/api/temporary-verifications/confirm", json={"temporary_id": temporary["temporary_id"], "code": temporary["verification_hint"]})
    assert confirmed.status_code == 200 and confirmed.json()["status"] == "VERIFIED"
    created = await client.post("/api/requests", json=payload, headers=headers)
    assert created.status_code == 201 and created.json()["verification_status"] == "TEMP_VERIFIED"
    authorized = await client.post(f"/api/requests/{created.json()['request_id']}/authorize-priority", headers=headers)
    assert authorized.status_code == 200 and authorized.json()["status"] == "ACTIVE"


async def test_management_permission_matrix_staff_lifecycle_and_audit(client):
    from backend.database import AsyncSessionLocal
    from backend.models import UserRecord
    admin = UserRecord(username="admin", password_hash=hash_password("admin-password"), role="ADMIN", management_id="LL-MGT-TEST0001")
    async with AsyncSessionLocal() as session:
        session.add(admin)
        await session.commit()
    ambulance = await register(client, "KHI-MGMT-01")
    ambulance_headers = {"Authorization": f"Bearer {ambulance['access_token']}"}
    assert (await client.get("/api/management/overview", headers=ambulance_headers)).status_code == 403
    dispatcher_headers = {"Authorization": f"Bearer {await login(client, 'dispatcher', 'dispatcher-password')}"}
    assert (await client.get("/api/management/overview", headers=dispatcher_headers)).status_code == 200
    assert (await client.get("/api/management/staff", headers=dispatcher_headers)).status_code == 403
    admin_headers = {"Authorization": f"Bearer {await login(client, 'admin', 'admin-password')}"}
    created = await client.post("/api/management/staff", headers=admin_headers, json={"username": "dispatcher-two", "password": "dispatcher-two-password", "role": "DISPATCHER"})
    assert created.status_code == 201
    staff = created.json()
    assert staff["management_id"].startswith("LL-MGT-")
    inactive = await client.patch(f"/api/management/staff/{staff['id']}", headers=admin_headers, json={"is_active": False})
    assert inactive.status_code == 200 and inactive.json()["is_active"] is False
    assert (await client.post("/api/auth/login", json={"username": "dispatcher-two", "password": "dispatcher-two-password"})).status_code == 403
    assert (await client.patch(f"/api/management/staff/{admin.id}", headers=admin_headers, json={"is_active": False})).status_code == 409
    logs = await client.get("/api/management/audit-logs", headers=admin_headers)
    assert logs.status_code == 200
    assert any(row["action"] == "staff.created" for row in logs.json())


async def test_migration_preserves_row_count_on_a_database_copy(tmp_path, monkeypatch):
    """Run init_db only against a copy and verify existing ambulance rows survive."""
    import backend.database as database

    source = Path("lifelane.db")
    copied = tmp_path / "lifelane-copy.db"
    shutil.copy2(source, copied)
    with sqlite3.connect(copied) as connection:
        before = connection.execute("SELECT count(*) FROM ambulances").fetchone()[0]
    migration_engine = create_async_engine(f"sqlite+aiosqlite:///{copied}")
    migration_factory = async_sessionmaker(migration_engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(database, "engine", migration_engine)
    monkeypatch.setattr(database, "AsyncSessionLocal", migration_factory)
    await database.init_db()
    with sqlite3.connect(copied) as connection:
        after = connection.execute("SELECT count(*) FROM ambulances").fetchone()[0]
        missing_ids = connection.execute("SELECT count(*) FROM ambulances WHERE lifelane_id IS NULL OR lifelane_id = ''").fetchone()[0]
    await migration_engine.dispose()
    assert after == before
    assert missing_ids == 0


def test_password_hash_is_salted_and_verifiable():
    first = hash_password("a-long-demo-password")
    assert first != hash_password("a-long-demo-password")
    assert verify_password("a-long-demo-password", first)
    assert not verify_password("wrong-password", first)
