"""Create the initial dispatcher/admin account from environment variables.

Run: SEED_ADMIN_USERNAME=dispatch SEED_ADMIN_PASSWORD='...' python -m backend.create_admin
On PowerShell set the variables with $env:SEED_ADMIN_USERNAME / $env:SEED_ADMIN_PASSWORD first.
"""
from __future__ import annotations
import asyncio
import secrets
from sqlalchemy import select
from backend.config import SEED_ADMIN_PASSWORD, SEED_ADMIN_USERNAME
from backend.database import AsyncSessionLocal, init_db
from backend.models import UserRecord
from backend.security import hash_password

async def create_admin() -> None:
    if not SEED_ADMIN_USERNAME or not SEED_ADMIN_PASSWORD:
        raise SystemExit("Set SEED_ADMIN_USERNAME and SEED_ADMIN_PASSWORD before creating an account.")
    if len(SEED_ADMIN_PASSWORD) < 10:
        raise SystemExit("SEED_ADMIN_PASSWORD must be at least 10 characters.")
    await init_db()
    async with AsyncSessionLocal() as db:
        existing = (await db.execute(select(UserRecord).where(UserRecord.username == SEED_ADMIN_USERNAME))).scalar_one_or_none()
        if existing:
            raise SystemExit("That username already exists.")
        db.add(UserRecord(username=SEED_ADMIN_USERNAME, password_hash=hash_password(SEED_ADMIN_PASSWORD), role="ADMIN", management_id=f"LL-MGT-{secrets.token_hex(4).upper()}"))
        await db.commit()
    print("Admin account created.")

if __name__ == "__main__":
    asyncio.run(create_admin())
