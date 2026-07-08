"""Automated ingestion of real Sakarya transport infrastructure and organized
industrial zone (OSB) data from OpenStreetMap, replacing the placeholder
highway/railway/industrial-zone/bus-stop entries seeded earlier.

Source: the public Overpass API (overpass-api.de), scoped to Sakarya
province's real administrative boundary (OSM relation 223462 - looked up
once via Nominatim; hardcoded here the same way the grid bounding box is in
app/core/city_bounds.py, rather than re-resolving it by name every run,
since name-based Overpass area lookups are slow/unreliable on the public
instance).

Pulls:
- Motorways/trunk roads (highway=motorway|trunk) -> Project(HIGHWAY)
- Rail lines (railway=rail) -> Project(RAILWAY)
- Named industrial landuse areas matching an OSB/"organize sanayi" naming
  pattern -> Project(INDUSTRIAL_ZONE) (individual factories are excluded -
  see osm_feature_parser.py)
- Bus stops/stations -> PointOfInterest(BUS_STOP)

OSM splits a single named road/rail line into many short segments; each
name's segments are averaged into one representative point, consistent with
the "one project = one point" model the scoring system already assumes.

Run with, from the backend/ directory:

    python scripts/ingest_sakarya_osm.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.infrastructure.ingestion.osm_feature_parser import (  # noqa: E402
    extract_highway_projects,
    extract_industrial_zone_projects,
    extract_railway_projects,
    extract_transit_pois,
)
from app.infrastructure.ingestion.overpass_client import OverpassClient  # noqa: E402
from app.infrastructure.persistence.database import SessionLocal  # noqa: E402
from app.infrastructure.persistence.models import (  # noqa: E402
    PointOfInterestModel,
    ProjectModel,
)
from app.infrastructure.persistence.repositories.point_of_interest_repository import (  # noqa: E402
    SqlAlchemyPointOfInterestRepository,
)
from app.infrastructure.persistence.repositories.project_repository import (  # noqa: E402
    SqlAlchemyProjectRepository,
)

CITY = "sakarya"
SAKARYA_ADMIN_AREA_ID = 3600223462  # OSM relation 223462 + Overpass area offset

OVERPASS_QUERY = f"""
[out:json][timeout:150];
area({SAKARYA_ADMIN_AREA_ID})->.sakarya;
(
  way["highway"~"motorway|trunk"](area.sakarya);
  way["railway"="rail"](area.sakarya);
  node["highway"="bus_stop"](area.sakarya);
  node["amenity"="bus_station"](area.sakarya);
  way["landuse"="industrial"]["name"](area.sakarya);
);
out center tags;
"""


def clear_superseded_placeholder_data(session) -> None:
    """Removes the earlier hand-seeded placeholder rows for the categories
    this script now provides real data for (highways, railways, industrial
    zones, bus stops). Ports and other categories are left untouched.
    """
    session.query(ProjectModel).filter(
        ProjectModel.city == CITY,
        ProjectModel.project_type.in_(["highway", "railway", "industrial_zone"]),
    ).delete(synchronize_session=False)
    session.query(PointOfInterestModel).filter(
        PointOfInterestModel.city == CITY,
        PointOfInterestModel.category == "bus_stop",
    ).delete(synchronize_session=False)
    session.commit()


def ingest() -> None:
    print("Querying Overpass for Sakarya transport + industrial zone data...")
    elements = OverpassClient().query(OVERPASS_QUERY)
    print(f"Got {len(elements)} raw OSM elements.\n")

    highways = extract_highway_projects(elements, CITY)
    railways = extract_railway_projects(elements, CITY)
    industrial = extract_industrial_zone_projects(elements, CITY)
    transit_pois = extract_transit_pois(elements, CITY)

    print(f"Highways/trunk roads: {len(highways)}")
    print(f"Rail lines: {len(railways)}")
    print(f"Organized industrial zones (OSB): {len(industrial)}")
    for project in industrial:
        print(f"  - {project.name}")
    print(f"Bus stops/stations: {len(transit_pois)}\n")

    session = SessionLocal()
    try:
        print("Clearing superseded placeholder data...")
        clear_superseded_placeholder_data(session)

        project_repo = SqlAlchemyProjectRepository(session)
        for project in [*highways, *railways, *industrial]:
            project_repo.add(project)

        poi_repo = SqlAlchemyPointOfInterestRepository(session)
        for poi in transit_pois:
            poi_repo.add(poi)
    finally:
        session.close()


if __name__ == "__main__":
    ingest()
    print("\nDone.")
