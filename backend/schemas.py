"""Pydantic schemas for LifeLane API."""
from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# ── Detection ────────────────────────────────────────────────────────────────

class DetectionResponse(BaseModel):
    id: str
    junction_id: str
    approach: Optional[str] = None
    is_siren: bool
    confidence: float
    model_type: str
    is_demo: bool
    audio_filename: Optional[str] = None
    warning: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Ambulance ─────────────────────────────────────────────────────────────────

class AmbulanceRegisterRequest(BaseModel):
    registration_number: str = Field(..., min_length=1)
    service_name: str = Field(..., min_length=1)
    device_id: str = Field(..., min_length=1)


class AmbulanceResponse(BaseModel):
    id: str
    lifelane_id: str
    registration_number: str
    service_name: str
    device_id: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Emergency Requests ────────────────────────────────────────────────────────

class EmergencyRequestCreate(BaseModel):
    ambulance_id: str
    origin_edge: str
    destination_edge: str
    hospital_id: str
    approach: str = "N"
    junction_id: str = "J1"
    emergency_mode: str = "EMERGENCY"


class EmergencyRequestResponse(BaseModel):
    id: str
    request_id: str
    ambulance_id: str
    origin_edge: str
    destination_edge: str
    hospital_id: str
    approach: str
    junction_id: str
    emergency_mode: str
    status: str
    route_json: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RequestStatusUpdate(BaseModel):
    status: str


# ── Signal Simulation ─────────────────────────────────────────────────────────

class SignalSimulateRequest(BaseModel):
    action: str = Field(..., description="request_priority | confirm_passage | cancel | reset")
    ambulance_id: Optional[str] = None
    approach: Optional[str] = None


class SignalStateResponse(BaseModel):
    junction_id: str
    state: str
    approach: Optional[str] = None
    ambulance_id: Optional[str] = None
    since: Optional[datetime] = None
    is_simulation: bool = True
    transitions_logged: int = 0


class JunctionStatus(BaseModel):
    junction_id: str
    state: str
    approach: Optional[str] = None
    ambulance_id: Optional[str] = None
    since: Optional[datetime] = None
    is_simulation: bool = True


# ── Health / Meta ─────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    db: str
    inference: str
    timestamp: datetime


class ModelInfoResponse(BaseModel):
    model_type: str
    is_synthetic: bool
    warning: Optional[str] = None
    classes: List[str]
    feature_dim: int


class StatsResponse(BaseModel):
    total_detections: int
    siren_detections: int
    total_ambulances: int
    total_requests: int
    pending_requests: int
    active_junctions: int
    signal_events: int


class EventResponse(BaseModel):
    id: str
    junction_id: str
    from_state: str
    to_state: str
    trigger: str
    ambulance_id: Optional[str] = None
    approach: Optional[str] = None
    is_simulation: bool
    created_at: datetime

    model_config = {"from_attributes": True}
