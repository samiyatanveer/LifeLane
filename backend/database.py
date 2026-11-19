"""SQLAlchemy async database setup."""
from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from backend.config import DATABASE_URL


engine = create_async_engine(DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Create all tables."""
    # Import models so they register with Base
    import backend.models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Lightweight SQLite migration for installations created before v2.1.
        # New tables are handled by create_all; these columns extend existing tables.
        for statement in (
            "ALTER TABLE ambulances ADD COLUMN contact_name VARCHAR(128)",
            "ALTER TABLE ambulances ADD COLUMN contact_phone VARCHAR(32)",
            "ALTER TABLE ambulances ADD COLUMN vehicle_type VARCHAR(64)",
            "ALTER TABLE requests ADD COLUMN verification_status VARCHAR(24) NOT NULL DEFAULT 'REGISTERED'",
            "ALTER TABLE requests ADD COLUMN expires_at DATETIME",
            "ALTER TABLE ambulances ADD COLUMN lifelane_id VARCHAR(64)",
            "ALTER TABLE users ADD COLUMN management_id VARCHAR(64)",
            "ALTER TABLE users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1",
        ):
            try:
                await conn.exec_driver_sql(statement)
            except Exception:  # column already exists / non-SQLite deployment
                pass
        # This project uses a small, idempotent SQLite migration rather than Alembic.
        # Backfill before adding indexes so no existing installation loses data.
        from backend.models import AmbulanceRecord, UserRecord
        import secrets
        from sqlalchemy import select
        # ORM backfill work runs after the DDL transaction below.
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(select(AmbulanceRecord))).scalars().all()
        occupied = {row.lifelane_id for row in rows if row.lifelane_id}
        for row in rows:
            if not row.lifelane_id:
                candidate = ""
                while not candidate or candidate in occupied:
                    candidate = f"LL-{secrets.token_hex(4).upper()}"
                row.lifelane_id = candidate
                occupied.add(candidate)
        # Versions before account linking stored LL-* here; map those values safely.
        by_public_id = {row.lifelane_id: row.id for row in rows}
        users = (await session.execute(select(UserRecord))).scalars().all()
        for user in users:
            if user.ambulance_id in by_public_id:
                user.ambulance_id = by_public_id[user.ambulance_id]
        management_ids = {user.management_id for user in users if user.management_id}
        for user in users:
            if user.role in {"DISPATCHER", "ADMIN"} and not user.management_id:
                candidate = ""
                while not candidate or candidate in management_ids:
                    candidate = f"LL-MGT-{secrets.token_hex(4).upper()}"
                user.management_id = candidate
                management_ids.add(candidate)
        await session.commit()
    async with engine.begin() as conn:
        await conn.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS ux_ambulances_lifelane_id ON ambulances (lifelane_id)")
        await conn.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS ux_ambulances_registration_number ON ambulances (registration_number)")
        # Enforce the public duplicate rule even when two normalized variants race.
        await conn.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS ux_ambulances_registration_normalized ON ambulances (upper(trim(registration_number)))")
        await conn.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS ux_users_management_id ON users (management_id)")
