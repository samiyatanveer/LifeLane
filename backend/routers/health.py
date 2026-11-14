"""Health and model info routers."""
from __future__ import annotations
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from backend.database import get_db
from backend.schemas import HealthResponse, ModelInfoResponse
from backend.config import API_VERSION
from backend.services.inference import get_inference_service

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(db: AsyncSession = Depends(get_db)):
    db_status = "ok"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"error: {exc}"

    svc = get_inference_service()
    inference_status = svc.model_type if svc._loaded else "not_loaded"

    return HealthResponse(
        status="ok",
        version=API_VERSION,
        db=db_status,
        inference=inference_status,
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/model-info", response_model=ModelInfoResponse)
async def model_info():
    svc = get_inference_service()
    info = svc.model_info()
    return ModelInfoResponse(**info)
