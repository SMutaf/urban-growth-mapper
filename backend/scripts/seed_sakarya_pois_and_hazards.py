"""Manually seeds a handful of Sakarya points of interest (transit/amenities)
and one earthquake hazard zone, per the MVP plan (manual data entry before any
scraping bot exists).

NOTE: coordinates below are approximate placeholders and must be verified
against real sources before being treated as fact. The earthquake hazard zone
reflects Sakarya's real, well-documented elevated seismic risk (the province
sits near the North Anatolian Fault and was heavily affected by the 1999
Marmara/Izmit earthquake) but its exact risk_level is a placeholder estimate,
not an AFAD-sourced figure.

Run with, from the backend/ directory:

    python scripts/seed_sakarya_pois_and_hazards.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.domain.entities.hazard_zone import HazardType, HazardZone  # noqa: E402
from app.domain.entities.point_of_interest import POICategory, PointOfInterest  # noqa: E402
from app.domain.entities.project import ProjectStatus  # noqa: E402
from app.infrastructure.persistence.database import SessionLocal  # noqa: E402
from app.infrastructure.persistence.repositories.hazard_zone_repository import (  # noqa: E402
    SqlAlchemyHazardZoneRepository,
)
from app.infrastructure.persistence.repositories.point_of_interest_repository import (  # noqa: E402
    SqlAlchemyPointOfInterestRepository,
)

SAMPLE_POIS = [
    PointOfInterest(
        id=None,
        name="Sakarya Egitim ve Arastirma Hastanesi",
        category=POICategory.HOSPITAL,
        status=ProjectStatus.COMPLETED,
        city="sakarya",
        latitude=40.7710,
        longitude=30.3830,
        importance=1.0,
    ),
    PointOfInterest(
        id=None,
        name="Sakarya Sehirlerarasi Otobus Terminali",
        category=POICategory.BUS_STOP,
        status=ProjectStatus.COMPLETED,
        city="sakarya",
        latitude=40.7610,
        longitude=30.3920,
        importance=0.9,
    ),
    PointOfInterest(
        id=None,
        name="Adapazari Carsi / Sehir Merkezi",
        category=POICategory.CITY_CENTER,
        status=ProjectStatus.COMPLETED,
        city="sakarya",
        latitude=40.7569,
        longitude=30.3781,
        importance=1.0,
    ),
]

SAMPLE_HAZARD_ZONES = [
    HazardZone(
        id=None,
        name="Kuzey Anadolu Fay Hatti - Sakarya bolgesi deprem riski",
        hazard_type=HazardType.EARTHQUAKE,
        risk_level=0.8,
        city="sakarya",
        latitude=40.7569,
        longitude=30.3781,
    ),
]


def seed() -> None:
    session = SessionLocal()
    try:
        poi_repo = SqlAlchemyPointOfInterestRepository(session)
        for poi in SAMPLE_POIS:
            poi_repo.add(poi)

        hazard_repo = SqlAlchemyHazardZoneRepository(session)
        for hazard_zone in SAMPLE_HAZARD_ZONES:
            hazard_repo.add(hazard_zone)
    finally:
        session.close()


if __name__ == "__main__":
    seed()
    print(
        f"Seeded {len(SAMPLE_POIS)} points of interest and "
        f"{len(SAMPLE_HAZARD_ZONES)} hazard zones for Sakarya."
    )
