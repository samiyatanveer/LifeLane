"""Import source-backed hospital records for the Lahore metropolitan bounding box.

Data source: OpenStreetMap contributors, queried through Overpass API.  Records are
stored as UNVERIFIED: OSM tags are useful directory leads, not operational verification.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from backend.database import AsyncSessionLocal, init_db
from backend.models import HospitalRecord

QUERY = '''[out:json][timeout:90];
(node["amenity"="hospital"](31.35,74.15,31.65,74.50);
 way["amenity"="hospital"](31.35,74.15,31.65,74.50);
 relation["amenity"="hospital"](31.35,74.15,31.65,74.50););
out center tags;'''
SOURCE_URL = "https://www.openstreetmap.org/copyright"


def download() -> list[dict]:
    request = Request(
        "https://overpass-api.de/api/interpreter",
        data=urlencode({"data": QUERY}).encode(),
        headers={"User-Agent": "LifeLane-directory-importer/1.0"},
    )
    with urlopen(request, timeout=120) as response:  # nosec B310: fixed public source
        return json.load(response)["elements"]


def field(tags: dict, *keys: str) -> str | None:
    return next((tags[key].strip() for key in keys if tags.get(key) and tags[key].strip()), None)


async def main() -> None:
    await init_db()
    imported = updated = skipped = 0
    async with AsyncSessionLocal() as session:
        for element in download():
            tags = element.get("tags", {})
            name = field(tags, "name:en", "name")
            point = element.get("center") or element
            latitude, longitude = point.get("lat"), point.get("lon")
            if not name or latitude is None or longitude is None:
                skipped += 1
                continue
            record_id = f"osm-{element['type']}-{element['id']}"
            address = field(tags, "addr:full") or ", ".join(filter(None, [field(tags, "addr:housenumber"), field(tags, "addr:street")])) or "Address not mapped in source"
            existing = (await session.execute(select(HospitalRecord).where(HospitalRecord.id == record_id))).scalar_one_or_none()
            values = dict(name=name, address=address, city="Lahore", province="Punjab", latitude=float(latitude), longitude=float(longitude), hospital_type="Hospital", contact_number=field(tags, "phone", "contact:phone"), verification_status="UNVERIFIED", is_active=True, source_name="OpenStreetMap contributors (ODbL) via Overpass API", source_url=SOURCE_URL)
            if existing:
                for key, value in values.items():
                    setattr(existing, key, value)
                updated += 1
            else:
                session.add(HospitalRecord(id=record_id, **values))
                imported += 1
        await session.commit()
    print(f"Imported {imported}, updated {updated}, skipped {skipped} Lahore OSM hospital records.")


if __name__ == "__main__":
    asyncio.run(main())
