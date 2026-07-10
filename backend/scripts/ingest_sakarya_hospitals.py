"""Automated ingestion of real Sakarya hospitals, replacing the single
hand-seeded placeholder hospital.

Source: veri.sakarya.bel.tr (Sakarya Buyuksehir Belediyesi's CKAN open-data
portal), the "Hastaneler" dataset's KMZ resource - real point coordinates,
no reprojection needed (unlike the mahalle boundaries file, this one is
already in plain WGS84 degrees).

Run with, from the backend/ directory:

    python scripts/ingest_sakarya_hospitals.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.domain.entities.point_of_interest import POICategory, PointOfInterest  # noqa: E402
from app.domain.entities.project import ProjectStatus  # noqa: E402
from app.infrastructure.ingestion.ckan_client import CkanClient  # noqa: E402
from app.infrastructure.ingestion.kmz_parser import parse_kmz_point_placemarks  # noqa: E402
from app.infrastructure.persistence.database import SessionLocal  # noqa: E402
from app.infrastructure.persistence.models import PointOfInterestModel  # noqa: E402
from app.infrastructure.persistence.repositories.point_of_interest_repository import (  # noqa: E402
    SqlAlchemyPointOfInterestRepository,
)

CKAN_BASE_URL = "https://veri.sakarya.bel.tr"
CITY = "sakarya"


def fetch_hospitals_kmz(client: CkanClient) -> bytes:
    for package in client.search_packages("Hastaneler", rows=5):
        kmz_resource = next(
            (r for r in package.get("resources", []) if r["url"].lower().endswith(".kmz")),
            None,
        )
        if kmz_resource:
            return client.download_resource(kmz_resource["url"])
    raise RuntimeError("Could not find a hospitals KMZ dataset on the portal")


def clear_placeholder_hospitals(session) -> None:
    session.query(PointOfInterestModel).filter(
        PointOfInterestModel.city == CITY,
        PointOfInterestModel.category == POICategory.HOSPITAL.value,
    ).delete(synchronize_session=False)
    session.commit()


def ingest() -> None:
    client = CkanClient(CKAN_BASE_URL)
    print("Downloading hospitals KMZ...")
    raw_kmz = fetch_hospitals_kmz(client)

    placemarks = parse_kmz_point_placemarks(raw_kmz)
    print(f"Parsed {len(placemarks)} hospitals.")

    session = SessionLocal()
    try:
        print("Clearing placeholder hospital data...")
        clear_placeholder_hospitals(session)

        repo = SqlAlchemyPointOfInterestRepository(session)
        for placemark in placemarks:
            name = placemark.properties.get("ad") or "Hastane"
            repo.add(
                PointOfInterest(
                    id=None,
                    name=name,
                    category=POICategory.HOSPITAL,
                    status=ProjectStatus.COMPLETED,
                    city=CITY,
                    latitude=placemark.latitude,
                    longitude=placemark.longitude,
                    importance=1.0,
                )
            )
            print(f"  {name} ({placemark.properties.get('ilce')})")
    finally:
        session.close()


if __name__ == "__main__":
    ingest()
    print("\nDone.")
