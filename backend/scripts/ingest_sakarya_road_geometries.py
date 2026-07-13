"""Ingests the real line geometry of Sakarya's named highways and railways,
for map display only - purely additive, does not touch or re-run
ingest_sakarya_osm.py's Project rows (the single averaged centroid point
per named road that CompositeHeatmapScorer's contributors depend on stays
exactly as it is - see app/domain/entities/road_geometry.py for why this
is a separate table rather than a change to that model).

Source: the same public Overpass API and Sakarya administrative area as
ingest_sakarya_osm.py, but queried with `out geom tags;` instead of
`out center tags;` so each way segment's full vertex list is kept instead
of being collapsed to one point.

Run with, from the backend/ directory:

    python scripts/ingest_sakarya_road_geometries.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.infrastructure.ingestion.osm_feature_parser import (  # noqa: E402
    extract_highway_geometries,
    extract_railway_geometries,
)
from app.infrastructure.ingestion.overpass_client import OverpassClient  # noqa: E402
from app.infrastructure.persistence.database import SessionLocal  # noqa: E402
from app.infrastructure.persistence.repositories.road_geometry_repository import (  # noqa: E402
    SqlAlchemyRoadGeometryRepository,
)

CITY = "sakarya"
SAKARYA_ADMIN_AREA_ID = 3600223462  # same OSM relation 223462 + Overpass area offset as ingest_sakarya_osm.py

OVERPASS_QUERY = f"""
[out:json][timeout:150];
area({SAKARYA_ADMIN_AREA_ID})->.sakarya;
(
  way["highway"~"motorway|trunk"]["name"](area.sakarya);
  way["railway"="rail"]["name"](area.sakarya);
);
out geom tags;
"""


def ingest() -> None:
    print("Querying Overpass for Sakarya highway/railway line geometry...")
    elements = OverpassClient().query(OVERPASS_QUERY)
    print(f"Got {len(elements)} raw OSM way segments.\n")

    highways = extract_highway_geometries(elements, CITY)
    railways = extract_railway_geometries(elements, CITY)

    print(f"Named highways: {len(highways)}")
    for road in highways:
        print(f"  - {road.name} ({len(road.segments)} segment(s))")
    print(f"Named railways: {len(railways)}")
    for road in railways:
        print(f"  - {road.name} ({len(road.segments)} segment(s))")

    session = SessionLocal()
    try:
        SqlAlchemyRoadGeometryRepository(session).bulk_replace(CITY, [*highways, *railways])
    finally:
        session.close()


if __name__ == "__main__":
    ingest()
    print("\nDone.")
