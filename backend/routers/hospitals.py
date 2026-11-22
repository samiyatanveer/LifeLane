"""Real-world hospital directory APIs. SUMO identifiers are never accepted here."""
from __future__ import annotations
import csv, io, uuid
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.models import HospitalRecord, UserRecord
from backend.security import current_user, require_roles

router = APIRouter(prefix="/hospitals", tags=["hospitals"])
PROVINCES = {"Punjab", "Sindh", "Khyber Pakhtunkhwa", "Balochistan", "Islamabad Capital Territory", "Gilgit-Baltistan", "Azad Jammu and Kashmir"}
FIELDS = ("name", "address", "city", "province", "latitude", "longitude", "hospital_type", "contact_number", "verification_status", "is_active", "source_name", "source_url")
REQUIRED = ("name", "address", "city", "province", "latitude", "longitude", "hospital_type")

def serialize(row):
    return {key: getattr(row, key) for key in ("id",) + FIELDS}

def validate(data):
    if any(data.get(key) is None or str(data.get(key)).strip() == "" for key in REQUIRED): raise HTTPException(422, "Hospital name, address, city, province, coordinates and type are required")
    if data["province"] not in PROVINCES: raise HTTPException(422, "Use a supported Pakistan province or territory")
    try: data["latitude"], data["longitude"] = float(data["latitude"]), float(data["longitude"])
    except (TypeError, ValueError): raise HTTPException(422, "Latitude and longitude must be numbers")
    if not -90 <= data["latitude"] <= 90 or not -180 <= data["longitude"] <= 180: raise HTTPException(422, "Coordinates are outside the valid range")

@router.get("")
async def list_hospitals(q: str | None = None, province: str | None = None, city: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), user: UserRecord = Depends(current_user), db: AsyncSession = Depends(get_db)):
    stmt = select(HospitalRecord).where(HospitalRecord.is_active == True)
    if q: stmt = stmt.where(or_(HospitalRecord.name.ilike(f"%{q}%"), HospitalRecord.city.ilike(f"%{q}%")))
    if province: stmt = stmt.where(HospitalRecord.province == province)
    if city: stmt = stmt.where(HospitalRecord.city.ilike(f"%{city}%"))
    rows = (await db.execute(stmt.order_by(HospitalRecord.name).offset((page-1)*page_size).limit(page_size+1))).scalars().all()
    return {"items": [serialize(row) for row in rows[:page_size]], "page": page, "page_size": page_size, "has_more": len(rows) > page_size, "coverage_notice": "Coverage is limited to imported source records; this does not claim complete Pakistan-wide coverage."}

@router.post("", status_code=201)
async def create_hospital(payload: dict, user: UserRecord = Depends(require_roles("DISPATCHER", "ADMIN")), db: AsyncSession = Depends(get_db)):
    validate(payload); row = HospitalRecord(id=payload.get("id") or str(uuid.uuid4()), **{key: payload.get(key) for key in FIELDS if key in payload})
    db.add(row); await db.flush(); return serialize(row)

@router.patch("/{hospital_id}")
async def update_hospital(hospital_id: str, payload: dict, user: UserRecord = Depends(require_roles("DISPATCHER", "ADMIN")), db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(HospitalRecord).where(HospitalRecord.id == hospital_id))).scalar_one_or_none()
    if not row: raise HTTPException(404, "Hospital not found")
    merged = {key: getattr(row, key) for key in REQUIRED}; merged.update(payload); validate(merged)
    for key, value in payload.items():
        if key in FIELDS: setattr(row, key, value)
    await db.flush(); return serialize(row)

@router.post("/import")
async def import_hospitals(file: UploadFile = File(...), user: UserRecord = Depends(require_roles("ADMIN")), db: AsyncSession = Depends(get_db)):
    if not (file.filename or "").lower().endswith(".csv"): raise HTTPException(422, "Upload a UTF-8 CSV file")
    try: rows = list(csv.DictReader(io.StringIO((await file.read()).decode("utf-8-sig"))))
    except UnicodeDecodeError: raise HTTPException(422, "CSV must be UTF-8 encoded")
    imported, errors = 0, []
    for number, data in enumerate(rows, 2):
        try:
            validate(data); db.add(HospitalRecord(id=data.get("id") or str(uuid.uuid4()), name=data["name"].strip(), address=data["address"].strip(), city=data["city"].strip(), province=data["province"].strip(), latitude=float(data["latitude"]), longitude=float(data["longitude"]), hospital_type=data["hospital_type"].strip(), contact_number=data.get("contact_number") or None, verification_status=data.get("verification_status") or "UNVERIFIED", is_active=str(data.get("is_active", "true")).lower() not in {"false", "0", "no"}, source_name=data.get("source_name") or None, source_url=data.get("source_url") or None)); imported += 1
        except HTTPException as exc: errors.append({"row": number, "error": exc.detail})
    await db.flush(); return {"imported": imported, "errors": errors}
