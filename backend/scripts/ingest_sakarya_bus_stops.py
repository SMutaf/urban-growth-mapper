"""Automated ingestion of real Sakarya bus stops, replacing the earlier
OpenStreetMap-derived ones. OSM's crowdsourced coverage turned out to be
badly incomplete for some districts (e.g. Hendek had ~1 stop in OSM vs
~20 visible on Google Maps) - this uses Sakarya Buyuksehir Belediyesi's own
live bus-tracking backend instead, which has real, officially maintained
stop data for every municipal/metrobus/ADARAY/minibus line.

Source: sbbpublicapi.sakarya.bel.tr - the API behind sakus.sakarya.bel.tr's
public live tracking map. Not formally documented, but requires no
authentication beyond an Origin/Referer header matching that public page
(see app/infrastructure/ingestion/sakarya_transit_client.py) - we call it
exactly as that public page already does.

There's no endpoint listing all line IDs, so this probes a fixed ID range
(confirmed empirically to cover every line: valid IDs run from 2 up to
~325, with some gaps for discontinued/unused IDs) and collects every real
line found. The same physical stop is referenced by multiple lines, so
stops are deduplicated by the API's own stop id before inserting.

Run with, from the backend/ directory:

    python scripts/ingest_sakarya_bus_stops.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.domain.entities.point_of_interest import POICategory, PointOfInterest  # noqa: E402
from app.domain.entities.project import ProjectStatus  # noqa: E402
from app.infrastructure.ingestion.sakarya_transit_client import SakaryaTransitClient  # noqa: E402
from app.infrastructure.ingestion.transit_stop_parser import extract_stops  # noqa: E402
from app.infrastructure.persistence.database import SessionLocal  # noqa: E402
from app.infrastructure.persistence.models import PointOfInterestModel  # noqa: E402
from app.infrastructure.persistence.repositories.point_of_interest_repository import (  # noqa: E402
    SqlAlchemyPointOfInterestRepository,
)

CITY = "sakarya"
LINE_ID_RANGE = range(1, 331)  # empirically covers every valid line (max seen: 325)


def fetch_all_stops(client: SakaryaTransitClient) -> dict:
    """Returns {stop_id: TransitStop}, deduplicated across every line that
    references the same physical stop.
    """
    stops_by_id = {}
    lines_found = 0
    for line_id in LINE_ID_RANGE:
        response = client.get_route_and_busstops(line_id)
        if response is None:
            continue
        lines_found += 1
        for stop in extract_stops(response):
            stops_by_id[stop.stop_id] = stop
    print(f"Found {lines_found} lines, {len(stops_by_id)} unique stops.")
    return stops_by_id


def clear_superseded_bus_stops(session) -> None:
    session.query(PointOfInterestModel).filter(
        PointOfInterestModel.city == CITY,
        PointOfInterestModel.category == POICategory.BUS_STOP.value,
    ).delete(synchronize_session=False)
    session.commit()


def ingest() -> None:
    client = SakaryaTransitClient()
    print("Probing Sakarya transit API for all lines and stops (this takes a few minutes)...")
    stops_by_id = fetch_all_stops(client)

    session = SessionLocal()
    try:
        print("Clearing OSM-sourced bus stop placeholders...")
        clear_superseded_bus_stops(session)

        repo = SqlAlchemyPointOfInterestRepository(session)
        for stop in stops_by_id.values():
            repo.add(
                PointOfInterest(
                    id=None,
                    name=stop.name,
                    category=POICategory.BUS_STOP,
                    status=ProjectStatus.COMPLETED,
                    city=CITY,
                    latitude=stop.latitude,
                    longitude=stop.longitude,
                    importance=1.0 if stop.is_smart_stop else 0.7,
                )
            )
    finally:
        session.close()


if __name__ == "__main__":
    ingest()
    print("\nDone.")
