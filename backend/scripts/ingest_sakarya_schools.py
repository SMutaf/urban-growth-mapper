"""One-time geocoding of Sakarya's 686 schools via the Google Geocoding API.

Source: veri.sakarya.bel.tr's "Sakarya Ilindeki Egitim Kurumlari" dataset -
school name, district, and a free-text address, but no coordinates. Unlike
the other ingestion scripts, this one calls a paid, rate-limited external
API (Google Geocoding, $5/1000 requests) rather than a free open-data
source, and does so deliberately as a single batch job: the resulting
coordinates are stored permanently in our own database and are not re-fetched
on every app visit or per end user. Re-run this only if the source address
list changes (e.g. a new school opens).

Requires GOOGLE_GEOCODING_API_KEY to be set in backend/.env.

Run with, from the backend/ directory:

    python scripts/ingest_sakarya_schools.py
"""

import sys
import time
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings  # noqa: E402
from app.domain.entities.point_of_interest import POICategory, PointOfInterest  # noqa: E402
from app.domain.entities.project import ProjectStatus  # noqa: E402
from app.infrastructure.ingestion.ckan_client import CkanClient  # noqa: E402
from app.infrastructure.ingestion.google_geocoding_client import GoogleGeocodingClient  # noqa: E402
from app.infrastructure.persistence.database import SessionLocal  # noqa: E402
from app.infrastructure.persistence.models import PointOfInterestModel  # noqa: E402
from app.infrastructure.persistence.repositories.point_of_interest_repository import (  # noqa: E402
    SqlAlchemyPointOfInterestRepository,
)

CKAN_BASE_URL = "https://veri.sakarya.bel.tr"
CITY = "sakarya"
REQUEST_DELAY_SECONDS = 0.1

# Google's high-precision results; anything else (a street/neighbourhood
# centroid rather than the actual building) gets a lower importance weight.
HIGH_PRECISION_LOCATION_TYPES = {"ROOFTOP", "RANGE_INTERPOLATED"}


def fetch_schools_xlsx(client: CkanClient) -> bytes:
    for package in client.search_packages("Egitim Kurumlari", rows=5):
        xlsx_resource = next(
            (r for r in package.get("resources", []) if r["url"].lower().endswith(".xlsx")),
            None,
        )
        if xlsx_resource:
            return client.download_resource(xlsx_resource["url"])
    raise RuntimeError("Could not find the schools XLSX dataset on the portal")


def parse_schools(xlsx_bytes: bytes):
    import io

    workbook = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))[1:]  # skip header
    for row in rows:
        _, il, ilce, okul_adi, adres = row[:5]
        if okul_adi and adres:
            yield ilce, okul_adi.strip(), adres.strip()


def already_geocoded_names(session) -> set:
    rows = (
        session.query(PointOfInterestModel.name)
        .filter(
            PointOfInterestModel.city == CITY,
            PointOfInterestModel.category == POICategory.SCHOOL.value,
        )
        .all()
    )
    return {row[0] for row in rows}


def ingest() -> None:
    settings = get_settings()
    if not settings.google_geocoding_api_key:
        raise RuntimeError("GOOGLE_GEOCODING_API_KEY is not set in backend/.env")

    ckan_client = CkanClient(CKAN_BASE_URL)
    geocoding_client = GoogleGeocodingClient(settings.google_geocoding_api_key)

    print("Downloading schools XLSX...")
    raw_xlsx = fetch_schools_xlsx(ckan_client)
    schools = list(parse_schools(raw_xlsx))
    print(f"Parsed {len(schools)} schools.")

    session = SessionLocal()
    try:
        # Resumable: a prior run may have partially succeeded (e.g. a
        # transient network failure mid-batch) - already-geocoded schools
        # are skipped rather than re-querying (and re-billing) for them.
        done = already_geocoded_names(session)
        remaining = [s for s in schools if s[1] not in done]
        print(f"{len(done)} already geocoded, {len(remaining)} remaining. Geocoding...\n")

        repo = SqlAlchemyPointOfInterestRepository(session)

        geocoded, failed = 0, 0
        for ilce, okul_adi, adres in remaining:
            result = geocoding_client.geocode(adres)
            time.sleep(REQUEST_DELAY_SECONDS)
            if result is None:
                failed += 1
                print(f"  FAIL {okul_adi} | {adres}")
                continue

            lat, lon, location_type = result
            importance = 1.0 if location_type in HIGH_PRECISION_LOCATION_TYPES else 0.6
            repo.add(
                PointOfInterest(
                    id=None,
                    name=okul_adi,
                    category=POICategory.SCHOOL,
                    status=ProjectStatus.COMPLETED,
                    city=CITY,
                    latitude=lat,
                    longitude=lon,
                    importance=importance,
                )
            )
            geocoded += 1

        print(f"\nGeocoded {geocoded}/{len(remaining)} remaining schools ({failed} failed).")
    finally:
        session.close()


if __name__ == "__main__":
    ingest()
    print("\nDone.")
