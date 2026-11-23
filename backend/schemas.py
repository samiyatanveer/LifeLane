"""Pydantic schemas for LifeLane API."""
from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
import re


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
    password: str = Field(..., min_length=8, max_length=128)
    contact_name: str = Field(..., min_length=2, max_length=128)
    contact_phone: str = Field(..., min_length=7, max_length=32)
    email: Optional[str] = Field(None, min_length=3, max_length=254)
    vehicle_type: str = Field(..., min_length=2, max_length=64)
    @field_validator("registration_number")
    @classmethod
    def registration_format(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z]{2,4}(?:-[A-Za-z0-9]{1,8})+", value.strip()):
            raise ValueError("Use a registration number like LEA-1234")
        return value
    @field_validator("contact_phone")
    @classmethod
    def phone_format(cls, value: str) -> str:
        if not re.fullmatch(r"\+?[0-9][0-9 ()-]{6,30}", value.strip()):
            raise ValueError("Enter a valid phone number")
        return value
    @field_validator("email")
    @classmethod
    def email_format(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address")
        return value
    @field_validator("password")
    @classmethod
    def password_policy(cls, value: str) -> str:
        if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
            raise ValueError("Password must contain at least one letter and one number")
        return value


class AmbulanceResponse(BaseModel):
    id: str
    lifelane_id: str
    registration_number: str
    service_name: str
    device_id: Optional[str] = None
    status: str
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    vehicle_type: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Emergency Requests ────────────────────────────────────────────────────────

class EmergencyRequestCreate(BaseModel):
    """A public emergency request, with legacy simulation inputs retained for staff tools."""
    # Kept for dispatcher/temporary workflows only. Ambulance accounts never use these.
    ambulance_id: Optional[str] = None
    origin_edge: Optional[str] = None
    destination_edge: Optional[str] = None
    hospital_id: str
    approach: Optional[str] = None
    junction_id: Optional[str] = None
    emergency_mode: str = "EMERGENCY"
    selected_route_id: Optional[str] = None
    emergency_notes: Optional[str] = Field(None, max_length=2000)
    origin_latitude: Optional[float] = Field(None, ge=-90, le=90)
    origin_longitude: Optional[float] = Field(None, ge=-180, le=180)
    origin_address: Optional[str] = Field(None, max_length=512)
    origin_city: Optional[str] = Field(None, max_length=128)
    location_source: Optional[str] = Field(None, pattern="^(GPS|MANUAL)$")

    @field_validator("emergency_mode")
    @classmethod
    def emergency_mode_allowed(cls, value: str) -> str:
        value = value.strip().upper()
        if value not in {"EMERGENCY", "URGENT", "ROUTINE"}:
            raise ValueError("Emergency type must be EMERGENCY, URGENT, or ROUTINE")
        return value


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
    verification_status: str = "REGISTERED"
    emergency_notes: Optional[str] = None
    origin_latitude: Optional[float] = None
    origin_longitude: Optional[float] = None
    origin_address: Optional[str] = None
    origin_city: Optional[str] = None
    location_source: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RequestStatusUpdate(BaseModel):
    status: str


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=128)
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("username", "password")
    @classmethod
    def login_fields_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("This field is required")
        return value

class PasswordRecoveryRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def recovery_email_format(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address")
        return value

class PasswordResetRequest(BaseModel):
    token: str = Field(..., min_length=20, max_length=256)
    password: str = Field(..., min_length=8, max_length=128)
    @field_validator("password")
    @classmethod
    def reset_password_policy(cls, value: str) -> str:
        if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
            raise ValueError("Password must contain at least one letter and one number")
        return value

class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def new_password_policy(cls, value: str) -> str:
        if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
            raise ValueError("Password must contain at least one letter and one number")
        return value


class UserResponse(BaseModel):
    id: str
    username: str
    role: str
    ambulance_id: Optional[str] = None
    ambulance: Optional[AmbulanceResponse] = None
    management_id: Optional[str] = None
    is_active: bool
    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserResponse


class StaffCreateRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=128)
    email: Optional[str] = Field(None, min_length=3, max_length=254)
    password: str = Field(..., min_length=10, max_length=128)
    role: str = Field(..., pattern="^(DISPATCHER|ADMIN)$")

    @field_validator("email")
    @classmethod
    def staff_email_format(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address")
        return value


class StaffUpdateRequest(BaseModel):
    role: Optional[str] = Field(None, pattern="^(DISPATCHER|ADMIN)$")
    is_active: Optional[bool] = None


class AuditLogResponse(BaseModel):
    id: str
    actor_id: Optional[str] = None
    action: str
    target: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class AmbulanceRegistrationResponse(TokenResponse):
    """Registration returns both the session and the newly issued public ID."""
    lifelane_id: str
    ambulance: AmbulanceResponse


class RouteOption(BaseModel):
    id: str
    label: str
    eta_minutes: int
    distance_km: float
    junctions: List[str]
    recommended: bool = False


class TemporaryVerificationStart(BaseModel):
    contact_phone: str = Field(..., min_length=7, max_length=32)
    vehicle_registration: str = Field(..., min_length=2, max_length=32)
    verification_method: str = Field(default="SMS", pattern="^(SMS|DEVICE)$")


class TemporaryVerificationConfirm(BaseModel):
    temporary_id: str
    code: str = Field(..., min_length=6, max_length=6)


class TemporaryVerificationResponse(BaseModel):
    temporary_id: str
    status: str
    expires_at: datetime
    verification_hint: Optional[str] = None


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
    active_requests: int
    completed_requests: int
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
