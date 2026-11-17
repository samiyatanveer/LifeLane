"""Detection endpoints."""
from __future__ import annotations
import uuid
from typing import Optional, List

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import DetectionEvent
from backend.schemas import DetectionResponse
from backend.services.inference import get_inference_service

router = APIRouter(tags=["detection"])


@router.post("/detect", response_model=DetectionResponse, status_code=201)
async def detect(
    file: UploadFile = File(...),
    approach: Optional[str] = Form(None),
    junction_id: str = Form("J1"),
    db: AsyncSession = Depends(get_db),
):
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    svc = get_inference_service()
    try:
        result = svc.predict(audio_bytes, file.filename or "audio.wav", approach, junction_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    event = DetectionEvent(
        id=result["id"],
        junction_id=result["junction_id"],
        approach=result["approach"],
        is_siren=result["is_siren"],
        confidence=result["confidence"],
        model_type=result["model_type"],
        is_demo=result["is_demo"],
        audio_filename=result["audio_filename"],
    )
    db.add(event)
    await db.flush()

    return DetectionResponse(
        **{k: v for k, v in result.items()},
        created_at=event.created_at,
    )


@router.get("/detections", response_model=List[DetectionResponse])
async def list_detections(
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    junction_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(DetectionEvent).order_by(DetectionEvent.created_at.desc())
    if junction_id:
        stmt = stmt.where(DetectionEvent.junction_id == junction_id)
    stmt = stmt.offset(offset).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()

    svc = get_inference_service()
    warning = svc._warning()

    return [
        DetectionResponse(
            id=r.id,
            junction_id=r.junction_id,
            approach=r.approach,
            is_siren=r.is_siren,
            confidence=r.confidence,
            model_type=r.model_type,
            is_demo=r.is_demo,
            audio_filename=r.audio_filename,
            warning=warning if r.model_type in ("SYNTHETIC", "MOCK_YAMNET") else None,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.delete("/detections/{detection_id}", status_code=204)
async def delete_detection(detection_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        delete(DetectionEvent).where(DetectionEvent.id == detection_id)
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Detection not found")
    return Response(status_code=204)
