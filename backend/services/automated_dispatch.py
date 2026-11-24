"""Backend-controlled emergency dispatch lifecycle.

The internal signal adapter is invoked only after identity, location and
destination validation; it never treats siren detection as authorization.
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from backend.models import NotificationRecord, RequestRecord, RequestTransitionRecord
from backend.services.simulation import get_simulation_service

TERMINAL = {"COMPLETED", "FAILED", "REJECTED", "CANCELLED", "ESCALATED"}
VALID_NEXT = {
    "PENDING": {"VALIDATING", "REJECTED", "EXPIRED", "CANCELLED", "ESCALATED"},
    "VALIDATING": {"AUTHORIZED", "FAILED", "REJECTED", "EXPIRED", "ESCALATED"},
    "AUTHORIZED": {"ROUTE_PREPARATION", "FAILED", "CANCELLED", "ESCALATED"},
    "ROUTE_PREPARATION": {"SIGNAL_COORDINATION", "FAILED", "ESCALATED"},
    "SIGNAL_COORDINATION": {"CORRIDOR_READY", "FAILED", "ESCALATED"},
    "CORRIDOR_READY": {"AMBULANCE_PASSAGE", "FAILED", "CANCELLED", "EXPIRED", "ESCALATED"},
    "AMBULANCE_PASSAGE": {"COMPLETED", "FAILED", "ESCALATED"},
}
async def transition(db: AsyncSession, request: RequestRecord, status: str, detail: str, user_id: str | None = None) -> None:
    previous = request.status
    if status not in VALID_NEXT.get(previous, set()):
        raise ValueError(f"Invalid request transition {previous} -> {status}")
    request.status, request.updated_at = status, datetime.now(timezone.utc)
    db.add(RequestTransitionRecord(request_id=request.request_id, from_status=previous, to_status=status, detail=detail))
    if user_id:
        db.add(NotificationRecord(user_id=user_id, request_id=request.request_id, message=detail))
    await db.flush()

async def process_request(db: AsyncSession, request: RequestRecord, user_id: str | None = None) -> None:
    """Advance one request; each operation completes before its transition is written."""
    request.processing_attempts = (request.processing_attempts or 0) + 1
    request.processing_error = None
    try:
        if request.status == "PENDING":
            await transition(db, request, "VALIDATING", "Validated authenticated ambulance, registered identity, GPS/location, emergency details and active destination.", user_id)
            await transition(db, request, "AUTHORIZED", "Backend safety validation succeeded; no siren signal was used as authorization.", user_id)
        if request.status == "AUTHORIZED":
            if not request.route_json:
                raise RuntimeError("route preparation has no selected route")
            await transition(db, request, "ROUTE_PREPARATION", "Selected route preparation succeeded.", user_id)
        if request.status == "ROUTE_PREPARATION":
            await transition(db, request, "SIGNAL_COORDINATION", "SUMO traffic simulation coordination requested; no physical signal claim made.", user_id)
            get_simulation_service().simulate_action(request.junction_id, "request_priority", request.ambulance_id, request.approach)
            await transition(db, request, "CORRIDOR_READY", "Simulated corridor is ready; passage still requires evidence.", user_id)
        if request.status == "CORRIDOR_READY":
            await confirm_passage(db, request, user_id or "system")
    except Exception as exc:
        request.processing_error = str(exc)
        await transition(db, request, "FAILED", f"Automatic processing failed: {exc}", user_id)
        await transition(db, request, "ESCALATED", "Automatic processing requires management review after retry exhaustion.", user_id)

_locks: dict[str, asyncio.Lock] = {}
_worker_task: asyncio.Task | None = None

async def enqueue_request(request_id: str, session_factory: async_sessionmaker, user_id: str | None = None) -> None:
    # Let the request dependency finish closing its transaction before the
    # worker opens a second session (important for SQLite deployments).
    await asyncio.sleep(0)
    await process_request_by_id(request_id, session_factory, user_id)

async def enqueue_request(request_id: str, session_factory: async_sessionmaker, user_id: str | None = None) -> None:
    # Let the request dependency finish closing its transaction before the
    # worker opens a second session (important for SQLite deployments).
    await asyncio.sleep(0)
    await process_request_by_id(request_id, session_factory, user_id)

async def process_request_by_id(request_id: str, session_factory: async_sessionmaker, user_id: str | None = None) -> None:
    lock = _locks.setdefault(request_id, asyncio.Lock())
    async with lock:
        async with session_factory() as db:
            request = (await db.execute(select(RequestRecord).where(RequestRecord.request_id == request_id))).scalar_one_or_none()
            if not request or request.status in TERMINAL:
                return
            now = datetime.now(timezone.utc)
            if request.processing_lease_until and request.processing_lease_until > now:
                return
            request.processing_lease_until = now + timedelta(seconds=30)
            await db.commit()
            try:
                await process_request(db, request, user_id)
                request.processing_lease_until = None
                await db.commit()
            except Exception:
                await db.rollback()
                raise

async def _worker(session_factory: async_sessionmaker, interval: float) -> None:
    while True:
        try:
            async with session_factory() as db:
                rows = (await db.execute(select(RequestRecord).where(RequestRecord.status.not_in(list(TERMINAL))).order_by(RequestRecord.created_at).limit(25))).scalars().all()
            await asyncio.gather(*(process_request_by_id(row.request_id, session_factory) for row in rows))
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        await asyncio.sleep(interval)

def start_worker(session_factory: async_sessionmaker, interval: float = 0.25) -> asyncio.Task:
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_worker(session_factory, interval), name="lifelane-request-worker")
    return _worker_task

async def stop_worker() -> None:
    global _worker_task
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        await asyncio.gather(_worker_task, return_exceptions=True)
    _worker_task = None

async def authorize_and_coordinate(db: AsyncSession, request: RequestRecord, user_id: str) -> None:
    """Execute a bounded, observable workflow so failures cannot strand a request."""
    try:
        await transition(db, request, "VALIDATING", "Request submitted; validating ambulance identity, location and destination.", user_id)
        await transition(db, request, "AUTHORIZED", "Emergency request authorized by LifeLane safety rules.", user_id)
        await transition(db, request, "ROUTE_PREPARATION", "Preparing the priority route to the selected hospital.", user_id)
        await transition(db, request, "SIGNAL_COORDINATION", "Coordinating safe priority transitions on the internal traffic-control adapter.", user_id)
        # This remains SUMO/internal state only.  No public claim of real signal control is made.
        get_simulation_service().simulate_action(request.junction_id, "request_priority", request.ambulance_id, request.approach)
        await transition(db, request, "CORRIDOR_READY", "Priority corridor prepared. Continue only when it is safe to proceed.", user_id)
    except Exception as exc:
        # Persist a terminal operational outcome and let the request commit;
        # callers must never receive a transient 500 while the record vanishes.
        await transition(db, request, "FAILED", f"Automatic coordination failed: {exc}", user_id)
        await transition(db, request, "ESCALATED", "Management has been alerted and will review this failed request.", user_id)

async def confirm_passage(db: AsyncSession, request: RequestRecord, user_id: str) -> None:
    try:
        # SUMO is the only available passage-evidence source. It must succeed
        # before the lifecycle records passage or completion.
        get_simulation_service().simulate_action(request.junction_id, "confirm_passage", request.ambulance_id, request.approach)
        await transition(db, request, "AMBULANCE_PASSAGE", "SUMO simulation supplied passage evidence; no real-world passage is claimed.", user_id)
        await transition(db, request, "COMPLETED", "Emergency corridor completed and internal traffic state restored.", user_id)
    except Exception as exc:
        await transition(db, request, "FAILED", f"Passage recovery failed: {exc}", user_id)
        await transition(db, request, "ESCALATED", "Passage recovery requires management review.", user_id)

async def process_request(db: AsyncSession, request: RequestRecord, user_id: str | None = None) -> None:
    """Advance a request only after each operation succeeds."""
    request.processing_attempts = (request.processing_attempts or 0) + 1
    request.processing_error = None
    try:
        if request.status == "PENDING":
            await transition(db, request, "VALIDATING", "Authenticated ambulance, registration, location, emergency details and destination validated.", user_id)
            await transition(db, request, "AUTHORIZED", "Backend safety validation succeeded; siren detection was not used as authorization.", user_id)
        if request.status == "AUTHORIZED":
            if not request.route_json:
                raise RuntimeError("selected route is unavailable")
            await transition(db, request, "ROUTE_PREPARATION", "Selected route preparation succeeded.", user_id)
        if request.status == "ROUTE_PREPARATION":
            await transition(db, request, "SIGNAL_COORDINATION", "SUMO simulation coordination requested; no physical signal-control claim made.", user_id)
            get_simulation_service().simulate_action(request.junction_id, "request_priority", request.ambulance_id, request.approach)
            await transition(db, request, "CORRIDOR_READY", "Simulated corridor ready; passage still requires evidence.", user_id)
        if request.status == "CORRIDOR_READY":
            await confirm_passage(db, request, user_id or "system")
    except Exception as exc:
        request.processing_error = str(exc)
        await transition(db, request, "FAILED", f"Automatic processing failed: {exc}", user_id)
        await transition(db, request, "ESCALATED", "Automatic processing requires management review.", user_id)

_locks: dict[str, asyncio.Lock] = {}
_worker_task: asyncio.Task | None = None

async def process_request_by_id(request_id: str, session_factory: async_sessionmaker, user_id: str | None = None) -> None:
    lock = _locks.setdefault(request_id, asyncio.Lock())
    async with lock:
        async with session_factory() as db:
            request = (await db.execute(select(RequestRecord).where(RequestRecord.request_id == request_id))).scalar_one_or_none()
            if not request or request.status in TERMINAL:
                return
            now = datetime.now(timezone.utc)
            if request.processing_lease_until and request.processing_lease_until > now:
                return
            request.processing_lease_until = now + timedelta(seconds=30)
            await db.commit()
            await process_request(db, request, user_id)
            request.processing_lease_until = None
            await db.commit()

async def _worker(session_factory: async_sessionmaker, interval: float) -> None:
    while True:
        try:
            async with session_factory() as db:
                rows = (await db.execute(select(RequestRecord).where(RequestRecord.status.not_in(list(TERMINAL))).order_by(RequestRecord.created_at).limit(25))).scalars().all()
            await asyncio.gather(*(process_request_by_id(r.request_id, session_factory) for r in rows))
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        await asyncio.sleep(interval)

def start_worker(session_factory: async_sessionmaker, interval: float = 0.25) -> asyncio.Task:
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_worker(session_factory, interval), name="lifelane-request-worker")
    return _worker_task

async def stop_worker() -> None:
    global _worker_task
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        await asyncio.gather(_worker_task, return_exceptions=True)
    _worker_task = None
