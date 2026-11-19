"""Authenticated ambulance registry, temporary verification, and dispatch workflow."""
from __future__ import annotations
import hashlib
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.models import AmbulanceRecord, RequestRecord, TemporaryVerificationRecord, UserRecord
from backend.schemas import (AmbulanceRegisterRequest, AmbulanceResponse, EmergencyRequestCreate,
    EmergencyRequestResponse, RequestStatusUpdate, RouteOption, TemporaryVerificationConfirm,
    TemporaryVerificationResponse, TemporaryVerificationStart, AmbulanceRegistrationResponse)
from backend.security import create_token, current_user, hash_password, is_expired, require_roles
from backend.services.simulation import get_simulation_service

router = APIRouter(tags=["dispatch"])
VALID_REQUEST_STATUSES = {"PENDING", "ACTIVE", "COMPLETED", "CANCELLED", "EXPIRED"}

def _lifelane_id() -> str: return f"LL-{secrets.token_hex(4).upper()}"
def _device_id() -> str: return f"DEV-{secrets.token_hex(8).upper()}"
def _req_id() -> str: return f"REQ-{uuid.uuid4().hex[:10].upper()}"
def _temp_id() -> str: return f"TMP-{uuid.uuid4().hex[:8].upper()}"
def _routes(origin: str, destination: str) -> list[dict]:
    # Route choices mirror the simulated 2x2 topology; no real-world routing is performed.
    return [
        {"id": "fastest", "label": "Fastest corridor", "eta_minutes": 6, "distance_km": 3.8, "junctions": ["J1", "J2"], "recommended": True},
        {"id": "balanced", "label": "Balanced traffic route", "eta_minutes": 8, "distance_km": 4.5, "junctions": ["J1", "J3", "J4"], "recommended": False},
        {"id": "alternate", "label": "Alternate bypass", "eta_minutes": 10, "distance_km": 5.1, "junctions": ["J2", "J4"], "recommended": False},
    ]

@router.get("/routes/options", response_model=List[RouteOption])
async def route_options(origin_edge: str, destination_edge: str, user: UserRecord = Depends(current_user)):
    return _routes(origin_edge, destination_edge)

@router.get("/ambulances", response_model=List[AmbulanceResponse])
async def list_ambulances(user: UserRecord = Depends(require_roles("DISPATCHER", "ADMIN")), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(AmbulanceRecord).order_by(AmbulanceRecord.created_at.desc()))).scalars().all()
    return [AmbulanceResponse.model_validate(r) for r in rows]

@router.get("/ambulances/me", response_model=AmbulanceResponse)
async def own_ambulance(user: UserRecord = Depends(require_roles("AMBULANCE")), db: AsyncSession = Depends(get_db)):
    ambulance = (await db.execute(select(AmbulanceRecord).where(AmbulanceRecord.id == user.ambulance_id))).scalar_one_or_none()
    if not ambulance:
        raise HTTPException(status_code=404, detail="Linked ambulance not found")
    return AmbulanceResponse.model_validate(ambulance)

@router.post("/ambulances/register", response_model=AmbulanceRegistrationResponse, status_code=201)
async def register_ambulance(payload: AmbulanceRegisterRequest, db: AsyncSession = Depends(get_db)):
    normalized_registration = payload.registration_number.strip().upper()
    existing = (await db.execute(select(AmbulanceRecord).where(func.upper(func.trim(AmbulanceRecord.registration_number)) == normalized_registration))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="This vehicle is already registered with LifeLane. If this is your ambulance, please log in using your existing account or contact LifeLane management.")
    # The duplicate check opened a read transaction on SQLAlchemy's async session.
    await db.rollback()
    # The explicit transaction makes ambulance, account, link and session all-or-nothing.
    try:
        async with db.begin():
            now = datetime.now(timezone.utc)
            for _ in range(8):
                lifelane_id = _lifelane_id()
                taken = (await db.execute(select(AmbulanceRecord.id).where(AmbulanceRecord.lifelane_id == lifelane_id))).scalar_one_or_none()
                if not taken:
                    break
            else:
                raise HTTPException(status_code=503, detail="Could not issue a unique LifeLane ID")
            ambulance = AmbulanceRecord(id=str(uuid.uuid4()), lifelane_id=lifelane_id,
                registration_number=payload.registration_number, service_name=payload.service_name.strip(),
                device_id=_device_id(), status="ACTIVE", contact_name=payload.contact_name.strip(),
                contact_phone=payload.contact_phone.strip(), vehicle_type=payload.vehicle_type.strip(), created_at=now)
            db.add(ambulance)
            await db.flush()
            user = UserRecord(username=lifelane_id, password_hash=hash_password(payload.password), role="AMBULANCE", ambulance_id=ambulance.id)
            db.add(user)
            await db.flush()
            token, expires = await create_token(user, db)
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="This vehicle is already registered with LifeLane. If this is your ambulance, please log in using your existing account or contact LifeLane management.") from exc
    ambulance_response = AmbulanceResponse.model_validate(ambulance)
    user_response = {"id": user.id, "username": user.username, "role": user.role, "ambulance_id": user.ambulance_id,
                     "is_active": user.is_active, "ambulance": ambulance_response}
    return AmbulanceRegistrationResponse(access_token=token, expires_at=expires, user=user_response,
                                         lifelane_id=ambulance.lifelane_id, ambulance=ambulance_response)

@router.post("/temporary-verifications", response_model=TemporaryVerificationResponse, status_code=201)
async def start_temporary_verification(payload: TemporaryVerificationStart, db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    duplicate = (await db.execute(select(TemporaryVerificationRecord).where(
        TemporaryVerificationRecord.contact_phone == payload.contact_phone,
        TemporaryVerificationRecord.vehicle_registration == payload.vehicle_registration,
        TemporaryVerificationRecord.status == "PENDING",
        TemporaryVerificationRecord.expires_at > now))).scalar_one_or_none()
    if duplicate:
        raise HTTPException(status_code=409, detail="A verification is already pending for this vehicle")
    code, temporary_id, expires = f"{secrets.randbelow(1_000_000):06d}", _temp_id(), now + timedelta(minutes=10)
    db.add(TemporaryVerificationRecord(temporary_id=temporary_id, contact_phone=payload.contact_phone,
        vehicle_registration=payload.vehicle_registration, verification_code_hash=hash_password(code), status="PENDING", expires_at=expires))
    # Deliberately surfaced only in this simulation project instead of claiming a real SMS delivery.
    return TemporaryVerificationResponse(temporary_id=temporary_id, status="PENDING", expires_at=expires, verification_hint=code)

@router.post("/temporary-verifications/confirm", response_model=TemporaryVerificationResponse)
async def confirm_temporary_verification(payload: TemporaryVerificationConfirm, db: AsyncSession = Depends(get_db)):
    record = (await db.execute(select(TemporaryVerificationRecord).where(TemporaryVerificationRecord.temporary_id == payload.temporary_id))).scalar_one_or_none()
    if not record or is_expired(record.expires_at):
        raise HTTPException(status_code=410, detail="Temporary verification has expired")
    from backend.security import verify_password
    if not verify_password(payload.code, record.verification_code_hash):
        raise HTTPException(status_code=422, detail="Verification code is incorrect")
    record.status = "VERIFIED"
    await db.flush()
    return TemporaryVerificationResponse(temporary_id=record.temporary_id, status=record.status, expires_at=record.expires_at)

@router.get("/requests", response_model=List[EmergencyRequestResponse])
async def list_requests(user: UserRecord = Depends(current_user), db: AsyncSession = Depends(get_db)):
    stmt = select(RequestRecord).order_by(RequestRecord.created_at.desc())
    if user.role == "AMBULANCE":
        ambulance = (await db.execute(select(AmbulanceRecord).where(AmbulanceRecord.id == user.ambulance_id))).scalar_one_or_none()
        if not ambulance:
            raise HTTPException(status_code=404, detail="Linked ambulance not found")
        stmt = stmt.where(RequestRecord.ambulance_id == ambulance.lifelane_id)
    rows = (await db.execute(stmt)).scalars().all()
    return [EmergencyRequestResponse.model_validate(r) for r in rows]

@router.post("/requests", response_model=EmergencyRequestResponse, status_code=201)
async def create_request(payload: EmergencyRequestCreate, user: UserRecord = Depends(current_user), db: AsyncSession = Depends(get_db)):
    ambulance_id, verification_status, expires_at = payload.ambulance_id, "REGISTERED", None
    if user.role == "AMBULANCE":
        ambulance = (await db.execute(select(AmbulanceRecord).where(AmbulanceRecord.id == user.ambulance_id))).scalar_one_or_none()
        if not ambulance:
            raise HTTPException(status_code=404, detail="Linked ambulance not found")
        if payload.ambulance_id and payload.ambulance_id != ambulance.lifelane_id:
            raise HTTPException(status_code=403, detail="Ambulance identity must match the authenticated account")
        ambulance_id = ambulance.lifelane_id
    elif ambulance_id and user.role not in {"DISPATCHER", "ADMIN"}:
        raise HTTPException(status_code=403, detail="Cannot dispatch for another ambulance")
    if not ambulance_id:
        raise HTTPException(status_code=422, detail="Ambulance identity is required")
    if ambulance_id.startswith("TMP-"):
        temp = (await db.execute(select(TemporaryVerificationRecord).where(TemporaryVerificationRecord.temporary_id == ambulance_id))).scalar_one_or_none()
        if not temp or temp.status != "VERIFIED" or is_expired(temp.expires_at):
            raise HTTPException(status_code=403, detail="Temporary ambulance must be verified before dispatch")
        verification_status, expires_at = "TEMP_VERIFIED", temp.expires_at
    elif not (await db.execute(select(AmbulanceRecord).where(AmbulanceRecord.lifelane_id == ambulance_id))).scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Registered ambulance not found")
    chosen = next((route for route in _routes(payload.origin_edge, payload.destination_edge) if route["id"] == (payload.selected_route_id or "fastest")), None)
    if not chosen: raise HTTPException(status_code=422, detail="Selected route is unavailable")
    now = datetime.now(timezone.utc)
    record = RequestRecord(id=str(uuid.uuid4()), request_id=_req_id(), ambulance_id=ambulance_id, origin_edge=payload.origin_edge,
        destination_edge=payload.destination_edge, hospital_id=payload.hospital_id, approach=payload.approach, junction_id=payload.junction_id,
        emergency_mode=payload.emergency_mode, status="PENDING", route_json=json.dumps(chosen), verification_status=verification_status,
        expires_at=expires_at, created_at=now, updated_at=now)
    db.add(record); await db.flush()
    return EmergencyRequestResponse.model_validate(record)

@router.patch("/requests/{request_id}/status", response_model=EmergencyRequestResponse)
async def update_request_status(request_id: str, payload: RequestStatusUpdate, user: UserRecord = Depends(require_roles("DISPATCHER", "ADMIN")), db: AsyncSession = Depends(get_db)):
    if payload.status not in VALID_REQUEST_STATUSES: raise HTTPException(status_code=422, detail="Invalid request status")
    record = (await db.execute(select(RequestRecord).where(RequestRecord.request_id == request_id))).scalar_one_or_none()
    if not record: raise HTTPException(status_code=404, detail="Request not found")
    record.status, record.updated_at = payload.status, datetime.now(timezone.utc); await db.flush()
    return EmergencyRequestResponse.model_validate(record)

@router.post("/requests/{request_id}/authorize-priority", response_model=EmergencyRequestResponse)
async def authorize_priority(request_id: str, user: UserRecord = Depends(require_roles("DISPATCHER", "ADMIN")), db: AsyncSession = Depends(get_db)):
    record = (await db.execute(select(RequestRecord).where(RequestRecord.request_id == request_id))).scalar_one_or_none()
    if not record: raise HTTPException(status_code=404, detail="Request not found")
    if record.expires_at and is_expired(record.expires_at):
        record.status = "EXPIRED"; raise HTTPException(status_code=410, detail="Temporary request has expired")
    if record.verification_status not in {"REGISTERED", "TEMP_VERIFIED"}: raise HTTPException(status_code=403, detail="Identity verification is required")
    get_simulation_service().simulate_action(record.junction_id, "request_priority", record.ambulance_id, record.approach)
    record.status, record.updated_at = "ACTIVE", datetime.now(timezone.utc); await db.flush()
    return EmergencyRequestResponse.model_validate(record)
