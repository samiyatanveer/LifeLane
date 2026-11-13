"""SQLAlchemy ORM models for LifeLane."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class DetectionEvent(Base):
    __tablename__ = "detection_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    junction_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    approach: Mapped[str | None] = mapped_column(String(16), nullable=True)
    is_siren: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    model_type: Mapped[str] = mapped_column(String(32), nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    audio_filename: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class AmbulanceRecord(Base):
    __tablename__ = "ambulances"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    lifelane_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    registration_number: Mapped[str] = mapped_column(String(32), nullable=False)
    service_name: Mapped[str] = mapped_column(String(128), nullable=False)
    device_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class RequestRecord(Base):
    __tablename__ = "requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    request_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    ambulance_id: Mapped[str] = mapped_column(String(64), nullable=False)
    origin_edge: Mapped[str] = mapped_column(String(128), nullable=False)
    destination_edge: Mapped[str] = mapped_column(String(128), nullable=False)
    hospital_id: Mapped[str] = mapped_column(String(64), nullable=False)
    approach: Mapped[str] = mapped_column(String(16), nullable=False)
    junction_id: Mapped[str] = mapped_column(String(64), nullable=False)
    emergency_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="PENDING", nullable=False)
    route_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class SignalEventRecord(Base):
    __tablename__ = "signal_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    junction_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    from_state: Mapped[str] = mapped_column(String(32), nullable=False)
    to_state: Mapped[str] = mapped_column(String(32), nullable=False)
    trigger: Mapped[str] = mapped_column(String(64), nullable=False)
    ambulance_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approach: Mapped[str | None] = mapped_column(String(16), nullable=True)
    is_simulation: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
