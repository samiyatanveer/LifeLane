"""Authenticated ambulance registry, temporary verification, and dispatch workflow."""
from __future__ import annotations
import asyncio
import hashlib
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import List
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
import backend.database as database
from backend.config import OSRM_BASE_URL, ROUTING_TIMEOUT_SECONDS
from backend.models import AmbulanceRecord, HospitalRecord, NotificationRecord, RequestRecord, RequestTransitionRecord, TemporaryVerificationRecord, UserRecord
from backend.schemas import (AmbulanceRegisterRequest, AmbulanceResponse, EmergencyRequestCreate,
    EmergencyRequestResponse, RequestStatusUpdate, RouteOption, TemporaryVerificationConfirm,
    TemporaryVerificationResponse, TemporaryVerificationStart, AmbulanceRegistrationResponse)
from backend.security import create_token, current_user, hash_password, is_expired, require_roles
from backend.services.simulation import get_simulation_service
from backend.services.automated_dispatch import authorize_and_coordinate, confirm_passage, transition, enqueue_request

router = APIRouter(tags=["dispatch"])
VALID_REQUEST_STATUSES = {"PENDING", "VALIDATING", "AUTHORIZED", "ROUTE_PREPARATION", "SIGNAL_COORDINATION", "CORRIDOR_READY", "AMBULANCE_PASSAGE", "COMPLETED", "FAILED", "REJECTED", "CANCELLED", "ESCALATED", "ACTIVE", "EXPIRED"}

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

def _fetch_osrm_route(origin_lat: float, origin_lng: float, destination_lat: float, destination_lng: float) -> dict:
    """Fetch one real-world driving route without exposing a routing provider to the browser."""
    url = (
        f"{OSRM_BASE_URL}/route/v1/driving/"
        f"{origin_lng},{origin_lat};{destination_lng},{destination_lat}"
        "?overview=false&steps=false"
    )
    request = Request(url, headers={"User-Agent": "LifeLane-route-preview/1.0"})
    try:
        with urlopen(request, timeout=ROUTING_TIMEOUT_SECONDS) as response:  # nosec B310: configured routing endpoint
            data = json.load(response)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError("Routing service could not be reached") from exc
    if data.get("code") != "Ok" or not data.get("routes"):
        raise RuntimeError("No drivable route was found for these locations")
    return data["routes"][0]

@router.get("/routes/options", response_model=List[RouteOption])
async def route_options(origin_edge: str, destination_edge: str, user: UserRecord = Depends(current_user)):
    return _routes(origin_edge, destination_edge)

@router.post("/routes/preview")
async def route_preview(payload: dict, user: UserRecord = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """Preview a real-world driving route to an active directory hospital."""
    hospital_id = payload.get("hospital_id")
    hospital = (await db.execute(select(HospitalRecord).where(HospitalRecord.id == hospital_id, HospitalRecord.is_active == True))).scalar_one_or_none()
    if not hospital:
        raise HTTPException(status_code=404, detail="Selected hospital is unavailable")
    lat, lng = payload.get("origin_latitude"), payload.get("origin_longitude")
    if lat is None or lng is None:
        raise HTTPException(status_code=422, detail="Origin coordinates are required for a location preview")
    try:
        origin_lat, origin_lng = float(lat), float(lng)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Origin coordinates must be valid numbers")
    if not -90 <= origin_lat <= 90 or not -180 <= origin_lng <= 180:
        raise HTTPException(status_code=422, detail="Origin coordinates are outside the valid range")
    try:
        route = await asyncio.to_thread(_fetch_osrm_route, origin_lat, origin_lng, hospital.latitude, hospital.longitude)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=f"Live routing is temporarily unavailable: {exc}") from exc
    distance_km = round(float(route["distance"]) / 1000, 1)
    eta_minutes = max(1, round(float(route["duration"]) / 60))
    return {
        "origin": {"latitude": origin_lat, "longitude": origin_lng},
        "destination": {"id": hospital.id, "name": hospital.name, "latitude": hospital.latitude, "longitude": hospital.longitude},
        "routing_available": True,
        "distance_km": distance_km,
        "eta_minutes": eta_minutes,
        "provider": "OSRM",
        "message": f"Driving route to {hospital.name}: {distance_km:.1f} km, approximately {eta_minutes} minutes.",
    }

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
            user = UserRecord(username=lifelane_id, email=payload.email, password_hash=hash_password(payload.password), role="AMBULANCE", ambulance_id=ambulance.id)
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
    hospital = (await db.execute(select(HospitalRecord).where(HospitalRecord.id == payload.hospital_id, HospitalRecord.is_active == True))).scalar_one_or_none()
    if user.role == "AMBULANCE" and not hospital:
        raise HTTPException(status_code=422, detail="Select an active hospital from the LifeLane directory")
    if user.role == "AMBULANCE":
        if payload.origin_latitude is None or payload.origin_longitude is None or not payload.location_source:
            raise HTTPException(status_code=422, detail="Current GPS or manually selected location is required")
        duplicate = (await db.execute(
            select(RequestRecord.id).where(
                RequestRecord.ambulance_id == ambulance_id,
                RequestRecord.status.not_in(["COMPLETED", "FAILED", "REJECTED", "CANCELLED", "ESCALATED", "EXPIRED"]),
            )
        )).scalar_one_or_none()
        if duplicate:
            raise HTTPException(status_code=409, detail="This ambulance already has an active emergency request")
    if ambulance_id.startswith("TMP-"):
        temp = (await db.execute(select(TemporaryVerificationRecord).where(TemporaryVerificationRecord.temporary_id == ambulance_id))).scalar_one_or_none()
        if not temp or temp.status != "VERIFIED" or is_expired(temp.expires_at):
            raise HTTPException(status_code=403, detail="Temporary ambulance must be verified before dispatch")
        verification_status, expires_at = "TEMP_VERIFIED", temp.expires_at
    elif not (await db.execute(select(AmbulanceRecord).where(AmbulanceRecord.lifelane_id == ambulance_id))).scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Registered ambulance not found")
    # Internal adapter: the prototype grid remains a simulation-only execution layer.
    origin_edge = payload.origin_edge or "realworld-origin"
    destination_edge = payload.destination_edge or "realworld-destination"
    approach = payload.approach or "N"
    junction_id = payload.junction_id or "J1"
    chosen = next((route for route in _routes(origin_edge, destination_edge) if route["id"] == (payload.selected_route_id or "fastest")), None)
    if not chosen: raise HTTPException(status_code=422, detail="Selected route is unavailable")
    now = datetime.now(timezone.utc)
    record = RequestRecord(id=str(uuid.uuid4()), request_id=_req_id(), ambulance_id=ambulance_id, origin_edge=origin_edge,
        destination_edge=destination_edge, hospital_id=payload.hospital_id, approach=approach, junction_id=junction_id,
        emergency_mode=payload.emergency_mode, status="PENDING", route_json=json.dumps(chosen), verification_status=verification_status,
        emergency_notes=payload.emergency_notes, origin_latitude=payload.origin_latitude, origin_longitude=payload.origin_longitude,
        origin_address=payload.origin_address, origin_city=payload.origin_city, location_source=payload.location_source,
        expires_at=expires_at, created_at=now, updated_at=now)
    db.add(record); await db.flush()
    await db.commit()
    asyncio.create_task(enqueue_request(record.request_id, database.AsyncSessionLocal, user.id))
    return EmergencyRequestResponse.model_validate(record)

@router.get("/requests/{request_id}/transitions")
async def request_transitions(request_id: str, user: UserRecord = Depends(current_user), db: AsyncSession = Depends(get_db)):
    request = (await db.execute(select(RequestRecord).where(RequestRecord.request_id == request_id))).scalar_one_or_none()
    if not request: raise HTTPException(404, "Request not found")
    if user.role == "AMBULANCE":
        ambulance = (await db.execute(select(AmbulanceRecord).where(AmbulanceRecord.id == user.ambulance_id))).scalar_one_or_none()
        if not ambulance or request.ambulance_id != ambulance.lifelane_id: raise HTTPException(403, "Not permitted")
    rows = (await db.execute(select(RequestTransitionRecord).where(RequestTransitionRecord.request_id == request_id).order_by(RequestTransitionRecord.created_at))).scalars().all()
    return [{"from_status": row.from_status, "to_status": row.to_status, "detail": row.detail, "created_at": row.created_at} for row in rows]

@router.get("/notifications")
async def notifications(user: UserRecord = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(NotificationRecord).where(NotificationRecord.user_id == user.id).order_by(NotificationRecord.created_at.desc()).limit(50))).scalars().all()
    return [{"id": row.id, "request_id": row.request_id, "message": row.message, "created_at": row.created_at, "read_at": row.read_at} for row in rows]

@router.post("/requests/{request_id}/confirm-passage", response_model=EmergencyRequestResponse)
async def passage_confirmed(request_id: str, user: UserRecord = Depends(current_user), db: AsyncSession = Depends(get_db)):
    record = (await db.execute(select(RequestRecord).where(RequestRecord.request_id == request_id))).scalar_one_or_none()
    if not record: raise HTTPException(404, "Request not found")
    ambulance = (await db.execute(select(AmbulanceRecord).where(AmbulanceRecord.id == user.ambulance_id))).scalar_one_or_none() if user.role == "AMBULANCE" else None
    if user.role == "AMBULANCE" and (not ambulance or record.ambulance_id != ambulance.lifelane_id): raise HTTPException(403, "Not permitted")
    if record.status != "CORRIDOR_READY": raise HTTPException(409, "Passage can only be confirmed after the corridor is ready")
    await confirm_passage(db, record, user.id)
    return EmergencyRequestResponse.model_validate(record)

@router.patch("/requests/{request_id}/status", response_model=EmergencyRequestResponse)
async def update_request_status(request_id: str, payload: RequestStatusUpdate, user: UserRecord = Depends(require_roles("DISPATCHER", "ADMIN")), db: AsyncSession = Depends(get_db)):
    if payload.status not in {"CANCELLED", "ESCALATED"}: raise HTTPException(status_code=422, detail="Automated lifecycle states cannot be manually changed")
    record = (await db.execute(select(RequestRecord).where(RequestRecord.request_id == request_id))).scalar_one_or_none()
    if not record: raise HTTPException(status_code=404, detail="Request not found")
    try:
        await transition(db, record, payload.status, f"Exception action {payload.status} recorded by management.", user.id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return EmergencyRequestResponse.model_validate(record)

@router.post("/requests/{request_id}/authorize-priority", response_model=EmergencyRequestResponse)
async def authorize_priority(request_id: str, user: UserRecord = Depends(require_roles("DISPATCHER", "ADMIN")), db: AsyncSession = Depends(get_db)):
    raise HTTPException(status_code=409, detail="Requests are authorized automatically after backend validation; management supervises exceptions.")
