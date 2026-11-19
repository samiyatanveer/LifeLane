"""Staff-only management portal APIs backed entirely by LifeLane data."""
from __future__ import annotations
import secrets
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.config import AUTH_SHOW_RESET_LINKS
from backend.models import AmbulanceRecord, AuditLogRecord, PasswordResetTokenRecord, RequestRecord, TemporaryVerificationRecord, UserRecord
from backend.schemas import AmbulanceResponse, AuditLogResponse, EmergencyRequestResponse, StaffCreateRequest, StaffUpdateRequest, UserResponse
from backend.security import current_user, hash_password, require_roles

router = APIRouter(prefix="/management", tags=["management"])

def _management_id() -> str:
    return f"LL-MGT-{secrets.token_hex(4).upper()}"

def _user(user: UserRecord) -> UserResponse:
    return UserResponse(id=user.id, username=user.username, role=user.role, management_id=user.management_id, ambulance_id=user.ambulance_id, is_active=user.is_active)

def _audit(db: AsyncSession, actor: UserRecord, action: str, target: str | None = None) -> None:
    db.add(AuditLogRecord(actor_id=actor.id, action=action, target=target))

@router.get("/overview")
async def overview(user: UserRecord = Depends(require_roles("DISPATCHER", "ADMIN")), db: AsyncSession = Depends(get_db)):
    async def count(model, where=None):
        stmt = select(func.count()).select_from(model)
        if where is not None: stmt = stmt.where(where)
        return int((await db.execute(stmt)).scalar() or 0)
    return {"ambulances": await count(AmbulanceRecord), "requests": {"pending": await count(RequestRecord, RequestRecord.status == "PENDING"), "active": await count(RequestRecord, RequestRecord.status == "ACTIVE"), "completed": await count(RequestRecord, RequestRecord.status == "COMPLETED")}, "temporary_verifications": {"pending": await count(TemporaryVerificationRecord, TemporaryVerificationRecord.status == "PENDING"), "verified": await count(TemporaryVerificationRecord, TemporaryVerificationRecord.status == "VERIFIED")}}

@router.get("/ambulances", response_model=list[AmbulanceResponse])
async def ambulances(search: str | None = None, status: str | None = None, user: UserRecord = Depends(require_roles("DISPATCHER", "ADMIN")), db: AsyncSession = Depends(get_db)):
    stmt = select(AmbulanceRecord).order_by(AmbulanceRecord.created_at.desc())
    if search: stmt = stmt.where((AmbulanceRecord.lifelane_id.contains(search)) | (AmbulanceRecord.registration_number.contains(search)))
    if status: stmt = stmt.where(AmbulanceRecord.status == status)
    return [AmbulanceResponse.model_validate(row) for row in (await db.execute(stmt)).scalars().all()]

@router.get("/requests", response_model=list[EmergencyRequestResponse])
async def requests(status: str | None = None, ambulance_id: str | None = None, user: UserRecord = Depends(require_roles("DISPATCHER", "ADMIN")), db: AsyncSession = Depends(get_db)):
    stmt = select(RequestRecord).order_by(RequestRecord.created_at.desc())
    if status: stmt = stmt.where(RequestRecord.status == status)
    if ambulance_id: stmt = stmt.where(RequestRecord.ambulance_id == ambulance_id)
    return [EmergencyRequestResponse.model_validate(row) for row in (await db.execute(stmt)).scalars().all()]

@router.get("/temporary-verifications")
async def temporary_verifications(status: str | None = None, user: UserRecord = Depends(require_roles("DISPATCHER", "ADMIN")), db: AsyncSession = Depends(get_db)):
    stmt = select(TemporaryVerificationRecord).order_by(TemporaryVerificationRecord.created_at.desc())
    if status: stmt = stmt.where(TemporaryVerificationRecord.status == status)
    rows = (await db.execute(stmt)).scalars().all()
    return [{"temporary_id": row.temporary_id, "contact_phone": row.contact_phone, "vehicle_registration": row.vehicle_registration, "status": row.status, "expires_at": row.expires_at, "created_at": row.created_at} for row in rows]

@router.post("/temporary-verifications/{temporary_id}/decision")
async def verification_decision(temporary_id: str, approved: bool, user: UserRecord = Depends(require_roles("DISPATCHER", "ADMIN")), db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(TemporaryVerificationRecord).where(TemporaryVerificationRecord.temporary_id == temporary_id))).scalar_one_or_none()
    if not row: raise HTTPException(status_code=404, detail="Temporary verification not found")
    row.status = "VERIFIED" if approved else "REJECTED"
    _audit(db, user, "verification.approved" if approved else "verification.rejected", temporary_id)
    return {"temporary_id": row.temporary_id, "status": row.status}

@router.get("/staff", response_model=list[UserResponse])
async def staff(user: UserRecord = Depends(require_roles("ADMIN")), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(UserRecord).where(UserRecord.role.in_(["DISPATCHER", "ADMIN"])).order_by(UserRecord.created_at.desc()))).scalars().all()
    return [_user(row) for row in rows]

@router.post("/staff", response_model=UserResponse, status_code=201)
async def create_staff(payload: StaffCreateRequest, user: UserRecord = Depends(require_roles("ADMIN")), db: AsyncSession = Depends(get_db)):
    for _ in range(8):
        management_id = _management_id()
        if not (await db.execute(select(UserRecord.id).where(UserRecord.management_id == management_id))).scalar_one_or_none(): break
    else: raise HTTPException(status_code=503, detail="Could not issue management ID")
    row = UserRecord(id=str(uuid.uuid4()), username=payload.username.strip(), password_hash=hash_password(payload.password), role=payload.role, management_id=management_id, is_active=True)
    db.add(row)
    try: await db.flush()
    except IntegrityError as exc: raise HTTPException(status_code=409, detail="Username already exists") from exc
    _audit(db, user, "staff.created", row.id)
    return _user(row)

@router.patch("/staff/{user_id}", response_model=UserResponse)
async def update_staff(user_id: str, payload: StaffUpdateRequest, user: UserRecord = Depends(require_roles("ADMIN")), db: AsyncSession = Depends(get_db)):
    target = (await db.execute(select(UserRecord).where(UserRecord.id == user_id))).scalar_one_or_none()
    if not target or target.role == "AMBULANCE": raise HTTPException(status_code=404, detail="Staff account not found")
    removing_admin = target.role == "ADMIN" and ((payload.role and payload.role != "ADMIN") or payload.is_active is False)
    if removing_admin:
        active_admins = int((await db.execute(select(func.count()).select_from(UserRecord).where(UserRecord.role == "ADMIN", UserRecord.is_active == True))).scalar() or 0)
        if active_admins <= 1: raise HTTPException(status_code=409, detail="Cannot deactivate or demote the last active admin")
    if payload.role: target.role = payload.role
    if payload.is_active is not None: target.is_active = payload.is_active
    _audit(db, user, "staff.updated", target.id)
    return _user(target)

@router.get("/audit-logs", response_model=list[AuditLogResponse])
async def audit_logs(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), user: UserRecord = Depends(require_roles("ADMIN")), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(AuditLogRecord).order_by(AuditLogRecord.created_at.desc()).offset(offset).limit(limit))).scalars().all()
    return [AuditLogResponse.model_validate(row) for row in rows]

@router.post("/staff/{user_id}/password-reset-link")
async def staff_reset_link(user_id: str, user: UserRecord = Depends(require_roles("ADMIN")), db: AsyncSession = Depends(get_db)):
    target = (await db.execute(select(UserRecord).where(UserRecord.id == user_id, UserRecord.role.in_(["DISPATCHER", "ADMIN"])))).scalar_one_or_none()
    if not target: raise HTTPException(status_code=404, detail="Staff account not found")
    token = secrets.token_urlsafe(32)
    db.add(PasswordResetTokenRecord(user_id=target.id, token_hash=hashlib.sha256(token.encode()).hexdigest(), expires_at=datetime.now(timezone.utc) + timedelta(minutes=30)))
    _audit(db, user, "staff.password_reset_link_created", target.id)
    response = {"message": "Reset link created; share it through an approved channel."}
    if AUTH_SHOW_RESET_LINKS: response["reset_link"] = f"/reset-password?token={token}"
    return response
