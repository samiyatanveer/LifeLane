"""Password hashing, signed bearer tokens, and role dependencies for LifeLane."""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.config import AUTH_SECRET, AUTH_TOKEN_TTL_MINUTES
from backend.database import get_db
from backend.models import AuthSessionRecord, UserRecord

bearer = HTTPBearer(auto_error=False)
ITERATIONS = 310_000

def is_expired(value: datetime) -> bool:
    """SQLite may return naive timestamps even for timezone=True columns."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value < datetime.now(timezone.utc)

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"

def verify_password(password: str, stored: str) -> bool:
    try:
        _, rounds, salt, digest = stored.split("$")
        calculated = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.urlsafe_b64decode(salt), int(rounds))
        return hmac.compare_digest(calculated, base64.urlsafe_b64decode(digest))
    except (ValueError, TypeError):
        return False

def _encode(payload: dict) -> str:
    raw = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(AUTH_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{signature}"

def _decode(token: str) -> dict:
    try:
        raw, signature = token.split(".", 1)
        expected = hmac.new(AUTH_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        return json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token") from exc

async def create_token(user: UserRecord, db: AsyncSession) -> tuple[str, datetime]:
    expires = datetime.now(timezone.utc) + timedelta(minutes=AUTH_TOKEN_TTL_MINUTES)
    token_id = str(uuid.uuid4())
    db.add(AuthSessionRecord(user_id=user.id, token_id=token_id, expires_at=expires, revoked=False))
    await db.flush()
    return _encode({"sub": user.id, "jti": token_id, "exp": int(expires.timestamp()), "role": user.role}), expires

async def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> UserRecord:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authentication required", headers={"WWW-Authenticate": "Bearer"})
    payload = _decode(credentials.credentials)
    if payload.get("exp", 0) < datetime.now(timezone.utc).timestamp():
        raise HTTPException(status_code=401, detail="Session expired")
    session = (await db.execute(select(AuthSessionRecord).where(AuthSessionRecord.token_id == payload.get("jti")))).scalar_one_or_none()
    user = (await db.execute(select(UserRecord).where(UserRecord.id == payload.get("sub")))).scalar_one_or_none()
    if not session or session.revoked or is_expired(session.expires_at) or not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Session is no longer valid")
    return user

def require_roles(*roles: str):
    async def dependency(user: UserRecord = Depends(current_user)) -> UserRecord:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="You are not authorized for this action")
        return user
    return dependency
