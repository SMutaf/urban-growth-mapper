"""Automated ingestion of real Sakarya transport infrastructure, organized
industrial zone (OSB), port, train station, highway junction, and university
data from OpenStreetMap, replacing the placeholder entries seeded earlier.

Source: the public Overpass API (overpass-api.de), scoped to Sakarya
province's real administrative boundary (OSM relation 223462 - looked up
once via Nominatim; hardcoded here the same way the grid bounding box is in
app/core/city_bounds.py, rather than re-resolving it by name every run,
since name-based Overpass area lookups are slow/unreliable on the public
instance). Scoping to the real boundary (not a loose bounding box) matters
here in particular - Sakarya borders Kocaeli, which has several university
campuses of its own that a loose box would incorrectly pull in.

Pulls:
- Motorways/trunk roads (highway=motorway|trunk) -> Project(HIGHWAY)
- Rail lines (railway=rail) -> Project(RAILWAY)
- Named industrial landuse areas matching an OSB/"organize sanayi" naming
  pattern -> Project(INDUSTRIAL_ZONE) (individual factories are excluded -
  see osm_feature_parser.py)
- landuse=harbour areas -> Project(PORT)
- railway=station nodes -> PointOfInterest(TRAIN_STATION)
- highway=motorway_junction nodes -> PointOfInterest(HIGHWAY_JUNCTION)
- amenity=university -> PointOfInterest(UNIVERSITY)

The station/junction/university points feed the banded (non-monotonic)
scoring contributors added alongside this script - see
app/domain/scoring/contributors/{rail_station_access,highway_junction_access,
university_proximity}.py - which is why they're now ingested as discrete
points rather than folded into the line-segment averaging the
highway/railway Project rows use.

OSM splits a single named road/rail line into many short segments; each
name's segments are averaged into one representative point, consistent with
the "one project = one point" model the line-noise contributors assume.

NOTE: bus stops are deliberately NOT handled here - they're sourced from
Sakarya's own transit API instead (see scripts/ingest_sakarya_bus_stops.py).

Run with, from the backend/ directory:

    python scripts/ingest_sakarya_osm.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.infrastructure.ingestion.osm_feature_parser import (  # noqa: E402
    extract_highway_junctions,
    extract_highway_projects,
    extract_industrial_zone_projects,
    extract_port_projects,
    extract_railway_projects,
    extract_train_stations,
    extract_universities,
)
from app.infrastructure.ingestion.overpass_client import OverpassClient  # noqa: E402
from app.infrastructure.persistence.database import SessionLocal  # noqa: E402
from app.infrastructure.persistence.models import PointOfInterestModel, ProjectModel  # noqa: E402
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
  way["landuse"="industrial"]["name"](area.sakarya);
  way["landuse"="harbour"](area.sakarya);
  node["railway"="station"](area.sakarya);
  node["highway"="motorway_junction"](area.sakarya);
  nwr["amenity"="university"](area.sakarya);
);
out center tags;
"""

SUPERSEDED_PROJECT_TYPES = ["highway", "railway", "industrial_zone", "port"]
SUPERSEDED_POI_CATEGORIES = ["train_station", "highway_junction", "university"]


def clear_superseded_placeholder_data(session) -> None:
    session.query(ProjectModel).filter(
        ProjectModel.city == CITY,
        ProjectModel.project_type.in_(SUPERSEDED_PROJECT_TYPES),
    ).delete(synchronize_session=False)
    session.query(PointOfInterestModel).filter(
        PointOfInterestModel.city == CITY,
        PointOfInterestModel.category.in_(SUPERSEDED_POI_CATEGORIES),
    ).delete(synchronize_session=False)
    session.commit()


def ingest() -> None:
    print("Querying Overpass for Sakarya transport/industrial/port/station/junction/university data...")
    elements = OverpassClient().query(OVERPASS_QUERY)
    print(f"Got {len(elements)} raw OSM elements.\n")

    highways = extract_highway_projects(elements, CITY)
    railways = extract_railway_projects(elements, CITY)
    industrial = extract_industrial_zone_projects(elements, CITY)
    ports = extract_port_projects(elements, CITY)
    stations = extract_train_stations(elements, CITY)
    junctions = extract_highway_junctions(elements, CITY)
    universities = extract_universities(elements, CITY)

    print(f"Highways/trunk roads: {len(highways)}")
    print(f"Rail lines: {len(railways)}")
    print(f"Organized industrial zones (OSB): {len(industrial)}")
    for project in industrial:
        print(f"  - {project.name}")
    print(f"Ports: {len(ports)}")
    for project in ports:
        print(f"  - {project.name}")
    print(f"Train stations: {len(stations)}")
    for poi in stations:
        print(f"  - {poi.name}")
    print(f"Highway junctions: {len(junctions)}")
    print(f"Universities: {len(universities)}")
    for poi in universities:
        print(f"  - {poi.name}")

    session = SessionLocal()
    try:
        print("\nClearing superseded placeholder data...")
        clear_superseded_placeholder_data(session)

        project_repo = SqlAlchemyProjectRepository(session)
        for project in [*highways, *railways, *industrial, *ports]:
            project_repo.add(project)

        poi_repo = SqlAlchemyPointOfInterestRepository(session)
        for poi in [*stations, *junctions, *universities]:
            poi_repo.add(poi)
    finally:
        session.close()


if __name__ == "__main__":
    ingest()
    print("\nDone.")
