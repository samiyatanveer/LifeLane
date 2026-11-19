"""Authentication endpoints for dispatcher and registered ambulance accounts."""
from __future__ import annotations
import hashlib
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.config import AUTH_SHOW_RESET_LINKS
from backend.models import AmbulanceRecord, AuditLogRecord, AuthSessionRecord, PasswordResetTokenRecord, UserRecord
from backend.schemas import AmbulanceResponse, LoginRequest, PasswordRecoveryRequest, PasswordResetRequest, TokenResponse, UserResponse
from backend.security import bearer, create_token, current_user, verify_password, _decode

router = APIRouter(prefix="/auth", tags=["auth"])
_attempts = defaultdict(deque)

def _limited(key: str, limit: int = 5, window: int = 60) -> bool:
    now = time.monotonic(); bucket = _attempts[key]
    while bucket and bucket[0] < now - window: bucket.popleft()
    if len(bucket) >= limit: return True
    bucket.append(now); return False

def _client_key(request: Request, purpose: str) -> str:
    """Use the client address when available; do not trust forwarded headers here."""
    return f"{purpose}:{request.client.host if request.client else 'unknown'}"

async def user_response(user: UserRecord, db: AsyncSession) -> UserResponse:
    ambulance = None
    if user.ambulance_id:
        ambulance = (await db.execute(select(AmbulanceRecord).where(AmbulanceRecord.id == user.ambulance_id))).scalar_one_or_none()
    return UserResponse(id=user.id, username=user.username, role=user.role, management_id=user.management_id, ambulance_id=user.ambulance_id,
                        is_active=user.is_active, ambulance=AmbulanceResponse.model_validate(ambulance) if ambulance else None)

@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    if _limited(f"{_client_key(request, 'login')}:{payload.username.strip().lower()}", 30, 60):
        raise HTTPException(status_code=429, detail="Too many sign-in attempts. Please try again shortly.")
    identity = payload.username.strip()
    user = (await db.execute(select(UserRecord).where(or_(UserRecord.username == identity, (UserRecord.management_id == identity) & UserRecord.role.in_(["DISPATCHER", "ADMIN"]))))).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is inactive. Contact LifeLane management.")
    token, expires = await create_token(user, db)
    db.add(AuditLogRecord(actor_id=user.id, action="auth.login", target=user.id))
    return TokenResponse(access_token=token, expires_at=expires, user=await user_response(user, db))

@router.post("/logout", status_code=204)
async def logout(credentials: HTTPAuthorizationCredentials = Depends(bearer), user: UserRecord = Depends(current_user), db: AsyncSession = Depends(get_db)):
    token_id = _decode(credentials.credentials).get("jti")
    session = (await db.execute(select(AuthSessionRecord).where(AuthSessionRecord.user_id == user.id, AuthSessionRecord.token_id == token_id))).scalar_one_or_none()
    if session:
        session.revoked = True
    db.add(AuditLogRecord(actor_id=user.id, action="auth.logout", target=user.id))
    return None

@router.get("/me", response_model=UserResponse)
async def me(user: UserRecord = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await user_response(user, db)

@router.get("/availability")
async def availability(registration_number: str, request: Request, db: AsyncSession = Depends(get_db)):
    if _limited(_client_key(request, "availability"), 20): raise HTTPException(status_code=429, detail="Please try again shortly")
    normalized = registration_number.strip().upper()
    if not normalized:
        raise HTTPException(status_code=422, detail="Registration number is required")
    row = (await db.execute(select(AmbulanceRecord.id).where(func.upper(func.trim(AmbulanceRecord.registration_number)) == normalized))).scalar_one_or_none()
    return {"available": row is None}

@router.post("/forgot-password")
async def forgot_password(payload: PasswordRecoveryRequest, request: Request, db: AsyncSession = Depends(get_db)):
    if _limited(f"{_client_key(request, 'recovery')}:{payload.username.strip().lower()}", 5, 60): raise HTTPException(status_code=429, detail="Please try again shortly")
    # No email is configured.  Always return the same response to avoid account enumeration.
    return {"message": "If account recovery is available, LifeLane management will provide the next steps."}

@router.post("/reset-password")
async def reset_password(payload: PasswordResetRequest, db: AsyncSession = Depends(get_db)):
    digest = hashlib.sha256(payload.token.encode()).hexdigest(); now = datetime.now(timezone.utc)
    record = (await db.execute(select(PasswordResetTokenRecord).where(PasswordResetTokenRecord.token_hash == digest))).scalar_one_or_none()
    if not record or record.used_at or record.expires_at.replace(tzinfo=timezone.utc) < now:
        raise HTTPException(status_code=400, detail="This password reset link is invalid or expired")
    user = (await db.execute(select(UserRecord).where(UserRecord.id == record.user_id))).scalar_one_or_none()
    if not user or not user.is_active: raise HTTPException(status_code=400, detail="This password reset link is invalid or expired")
    user.password_hash = __import__("backend.security", fromlist=["hash_password"]).hash_password(payload.password)
    record.used_at = now
    await db.execute(update(AuthSessionRecord).where(AuthSessionRecord.user_id == user.id).values(revoked=True))
    db.add(AuditLogRecord(actor_id=user.id, action="auth.password_reset", target=user.id))
    return {"message": "Password updated. Please sign in again."}
