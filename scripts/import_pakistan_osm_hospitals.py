"""Import hospitals mapped in all Pakistan first-level OSM administrative areas.

Source: © OpenStreetMap contributors, ODbL. This imports mapped hospitals only;
it is not an official or exhaustive health-facility registry.
"""
from __future__ import annotations
import asyncio, json, sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from sqlalchemy import select
from backend.database import AsyncSessionLocal, init_db
from backend.models import HospitalRecord

AREAS = {
    "Punjab": "PK-PB", "Sindh": "PK-SD", "Khyber Pakhtunkhwa": "PK-KP",
    "Balochistan": "PK-BA", "Islamabad Capital Territory": "PK-IS",
    "Gilgit-Baltistan": "PK-GB", "Azad Jammu and Kashmir": "PK-JK",
}

def fetch(province_code: str) -> list[dict]:
    query = f'''[out:json][timeout:240];area["ISO3166-2"="{province_code}"][boundary=administrative]->.a;(node["amenity"="hospital"](area.a);way["amenity"="hospital"](area.a);relation["amenity"="hospital"](area.a););out center tags;'''
    body = urlencode({"data": query}).encode()
    errors = []
    for endpoint in ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"):
        request = Request(endpoint, data=body, headers={"User-Agent": "LifeLane-directory-importer/1.0"})
        try:
            with urlopen(request, timeout=300) as response:  # nosec B310 fixed public dataset source
                return json.load(response).get("elements", [])
        except (HTTPError, URLError, json.JSONDecodeError) as exc:
            errors.append(f"{endpoint}: {exc}")
    raise RuntimeError("; ".join(errors))

def value(tags, *keys): return next((str(tags[k]).strip() for k in keys if tags.get(k)), None)

async def main():
    await init_db(); added = updated = 0
    async with AsyncSessionLocal() as db:
        for province, code in AREAS.items():
            elements = fetch(code)
            for item in elements:
                tags, point = item.get("tags", {}), item.get("center") or item
                name, lat, lon = value(tags, "name:en", "name"), point.get("lat"), point.get("lon")
                if not name or lat is None or lon is None: continue
                record_id = f"osm-{item['type']}-{item['id']}"
                address = value(tags, "addr:full") or ", ".join(filter(None, [value(tags, "addr:housenumber"), value(tags, "addr:street")])) or "Address not mapped in source"
                city = value(tags, "addr:city", "addr:place") or "City not mapped in source"
                values = dict(name=name, address=address, city=city, province=province, latitude=float(lat), longitude=float(lon), hospital_type="Hospital", contact_number=value(tags, "phone", "contact:phone"), verification_status="UNVERIFIED", is_active=True, source_name="OpenStreetMap contributors (ODbL) via Overpass API", source_url="https://www.openstreetmap.org/copyright")
                existing = (await db.execute(select(HospitalRecord).where(HospitalRecord.id == record_id))).scalar_one_or_none()
                if existing:
                    for key, val in values.items(): setattr(existing, key, val)
                    updated += 1
                else:
                    db.add(HospitalRecord(id=record_id, **values)); added += 1
            await db.commit()
            print(f"{province}: processed {len(elements)} mapped entries")
    print(f"Added {added}, updated {updated} records.")

if __name__ == "__main__": asyncio.run(main())
