"""Signal simulation endpoints."""
from __future__ import annotations
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import DetectionEvent, AmbulanceRecord, RequestRecord, SignalEventRecord
from backend.schemas import (
    EventResponse,
    JunctionStatus,
    SignalSimulateRequest,
    SignalStateResponse,
    StatsResponse,
)
from backend.services.simulation import get_simulation_service

router = APIRouter(tags=["signals"])


@router.get("/signals", response_model=List[JunctionStatus])
async def list_signals():
    svc = get_simulation_service()
    return [JunctionStatus(**j) for j in svc.get_all_junctions()]


@router.post("/signals/{junction_id}/simulate", response_model=SignalStateResponse)
async def simulate_signal(junction_id: str, payload: SignalSimulateRequest):
    svc = get_simulation_service()
    try:
        result = svc.simulate_action(
            junction_id=junction_id,
            action=payload.action,
            ambulance_id=payload.ambulance_id,
            approach=payload.approach,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return SignalStateResponse(**result)


@router.get("/events", response_model=List[EventResponse])
async def list_events(db: AsyncSession = Depends(get_db)):
    """Return in-memory simulation events (most recent first)."""
    svc = get_simulation_service()
    events = svc.get_events()
    return [EventResponse(**e) for e in events]


@router.get("/stats", response_model=StatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db)):
    total_det = (await db.execute(select(func.count()).select_from(DetectionEvent))).scalar() or 0
    siren_det = (await db.execute(
        select(func.count()).select_from(DetectionEvent).where(DetectionEvent.is_siren == True)  # noqa: E712
    )).scalar() or 0
    total_amb = (await db.execute(select(func.count()).select_from(AmbulanceRecord))).scalar() or 0
    total_req = (await db.execute(select(func.count()).select_from(RequestRecord))).scalar() or 0
    pending_req = (await db.execute(
        select(func.count()).select_from(RequestRecord).where(RequestRecord.status == "PENDING")
    )).scalar() or 0

    svc = get_simulation_service()
    sim_stats = svc.get_stats()

    return StatsResponse(
        total_detections=int(total_det),
        siren_detections=int(siren_det),
        total_ambulances=int(total_amb),
        total_requests=int(total_req),
        pending_requests=int(pending_req),
        active_junctions=sim_stats["active_junctions"],
        signal_events=sim_stats["signal_events"],
    )
