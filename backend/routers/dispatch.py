"""Dispatch endpoints — ambulances and emergency requests."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import AmbulanceRecord, RequestRecord
from backend.schemas import (
    AmbulanceRegisterRequest,
    AmbulanceResponse,
    EmergencyRequestCreate,
    EmergencyRequestResponse,
    RequestStatusUpdate,
)

router = APIRouter(tags=["dispatch"])

VALID_REQUEST_STATUSES = {"PENDING", "ACTIVE", "COMPLETED", "CANCELLED"}


def _lifelane_id() -> str:
    return f"LL-{uuid.uuid4().hex[:8].upper()}"


def _req_id() -> str:
    return f"REQ-{uuid.uuid4().hex[:10].upper()}"


# ── Ambulances ────────────────────────────────────────────────────────────────

@router.get("/ambulances", response_model=List[AmbulanceResponse])
async def list_ambulances(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(AmbulanceRecord).order_by(AmbulanceRecord.created_at.desc()))).scalars().all()
    return [AmbulanceResponse.model_validate(r) for r in rows]


@router.post("/ambulances/register", response_model=AmbulanceResponse, status_code=201)
async def register_ambulance(payload: AmbulanceRegisterRequest, db: AsyncSession = Depends(get_db)):
    # Check device_id uniqueness
    existing = (await db.execute(
        select(AmbulanceRecord).where(AmbulanceRecord.device_id == payload.device_id)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail=f"Device ID '{payload.device_id}' already registered")

    record = AmbulanceRecord(
        id=str(uuid.uuid4()),
        lifelane_id=_lifelane_id(),
        registration_number=payload.registration_number,
        service_name=payload.service_name,
        device_id=payload.device_id,
        status="ACTIVE",
        created_at=datetime.now(timezone.utc),
    )
    db.add(record)
    await db.flush()
    return AmbulanceResponse.model_validate(record)


# ── Requests ─────────────────────────────────────────────────────────────────

@router.get("/requests", response_model=List[EmergencyRequestResponse])
async def list_requests(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(RequestRecord).order_by(RequestRecord.created_at.desc()))).scalars().all()
    return [EmergencyRequestResponse.model_validate(r) for r in rows]


@router.post("/requests", response_model=EmergencyRequestResponse, status_code=201)
async def create_request(payload: EmergencyRequestCreate, db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    record = RequestRecord(
        id=str(uuid.uuid4()),
        request_id=_req_id(),
        ambulance_id=payload.ambulance_id,
        origin_edge=payload.origin_edge,
        destination_edge=payload.destination_edge,
        hospital_id=payload.hospital_id,
        approach=payload.approach,
        junction_id=payload.junction_id,
        emergency_mode=payload.emergency_mode,
        status="PENDING",
        route_json=None,
        created_at=now,
        updated_at=now,
    )
    db.add(record)
    await db.flush()
    return EmergencyRequestResponse.model_validate(record)


@router.patch("/requests/{request_id}/status", response_model=EmergencyRequestResponse)
async def update_request_status(
    request_id: str,
    payload: RequestStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    if payload.status not in VALID_REQUEST_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid status. Must be one of {VALID_REQUEST_STATUSES}")

    record = (await db.execute(
        select(RequestRecord).where(RequestRecord.request_id == request_id)
    )).scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Request not found")

    record.status = payload.status
    record.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return EmergencyRequestResponse.model_validate(record)
