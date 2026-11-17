"""Seed demo data into an empty database."""
from __future__ import annotations
import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import select


async def seed():
    # Import here to ensure app context
    from backend.database import AsyncSessionLocal, init_db
    from backend.models import AmbulanceRecord, RequestRecord

    await init_db()

    async with AsyncSessionLocal() as session:
        count = (await session.execute(select(AmbulanceRecord))).scalars().first()
        if count is not None:
            print("DB already seeded — skipping.")
            return

        now = datetime.now(timezone.utc)
        ambulances = [
            AmbulanceRecord(
                id=str(uuid.uuid4()),
                lifelane_id="LL-DEMO0001",
                registration_number="KA-01-AB-1234",
                service_name="City Emergency Services",
                device_id="DEVICE-DEMO-001",
                status="ACTIVE",
                created_at=now,
            ),
            AmbulanceRecord(
                id=str(uuid.uuid4()),
                lifelane_id="LL-DEMO0002",
                registration_number="KA-01-CD-5678",
                service_name="Metro Ambulance Corp",
                device_id="DEVICE-DEMO-002",
                status="ACTIVE",
                created_at=now,
            ),
            AmbulanceRecord(
                id=str(uuid.uuid4()),
                lifelane_id="LL-DEMO0003",
                registration_number="KA-02-EF-9012",
                service_name="Rapid Response Unit",
                device_id="DEVICE-DEMO-003",
                status="ACTIVE",
                created_at=now,
            ),
        ]
        for amb in ambulances:
            session.add(amb)
        await session.flush()

        requests = [
            RequestRecord(
                id=str(uuid.uuid4()),
                request_id="REQ-DEMO-0001",
                ambulance_id=ambulances[0].lifelane_id,
                origin_edge="EDGE-N-001",
                destination_edge="EDGE-S-099",
                hospital_id="HOSP-CENTRAL",
                approach="N",
                junction_id="J1",
                emergency_mode="EMERGENCY",
                status="COMPLETED",
                route_json=None,
                created_at=now,
                updated_at=now,
            ),
            RequestRecord(
                id=str(uuid.uuid4()),
                request_id="REQ-DEMO-0002",
                ambulance_id=ambulances[1].lifelane_id,
                origin_edge="EDGE-E-012",
                destination_edge="EDGE-W-033",
                hospital_id="HOSP-NORTH",
                approach="E",
                junction_id="J2",
                emergency_mode="EMERGENCY",
                status="PENDING",
                route_json=None,
                created_at=now,
                updated_at=now,
            ),
        ]
        for req in requests:
            session.add(req)
        await session.commit()
        print(f"Seeded {len(ambulances)} ambulances and {len(requests)} requests.")


if __name__ == "__main__":
    asyncio.run(seed())
