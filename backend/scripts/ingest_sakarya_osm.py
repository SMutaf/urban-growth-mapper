"""Automated ingestion of real Sakarya transport infrastructure, organized
industrial zone (OSB), port, train station, highway junction, university,
and building-density/open-land data from OpenStreetMap, replacing the
placeholder entries seeded earlier.

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
- amenity=prison, landuse=landfill, amenity=grave_yard|landuse=cemetery ->
  PointOfInterest(PRISON|LANDFILL|CEMETERY) - LULU (locally unwanted land
  use) data for NegativeExternalityContributor
- building=* and landuse=farmland|meadow|grass -> LandCoverCell, one per
  lattice point on the same ~1km grid the production heatmap itself uses
  (not one row per building - see osm_feature_parser.aggregate_land_cover
  and app/domain/entities/land_cover.py for why), feeding
  FringeContributor's urban-rural fringe signal
  (app/domain/scoring/contributors/fringe.py).

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

from app.core.city_bounds import CITY_BOUNDING_BOXES, load_city_boundary  # noqa: E402
from app.domain.grid.grid_generator import GridGenerator  # noqa: E402
from app.infrastructure.ingestion.osm_feature_parser import (  # noqa: E402
    aggregate_land_cover,
    extract_highway_junctions,
    extract_highway_projects,
    extract_industrial_zone_projects,
    extract_negative_externalities,
    extract_port_projects,
    extract_railway_projects,
    extract_train_stations,
    extract_universities,
)
from app.infrastructure.ingestion.overpass_client import OverpassClient  # noqa: E402
from app.infrastructure.persistence.database import SessionLocal  # noqa: E402
from app.infrastructure.persistence.models import PointOfInterestModel, ProjectModel  # noqa: E402
from app.infrastructure.persistence.repositories.land_cover_repository import (  # noqa: E402
    SqlAlchemyLandCoverRepository,
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
  way["landuse"="industrial"]["name"](area.sakarya);
  way["landuse"="harbour"](area.sakarya);
  node["railway"="station"](area.sakarya);
  node["highway"="motorway_junction"](area.sakarya);
  nwr["amenity"="university"](area.sakarya);
  nwr["amenity"="prison"](area.sakarya);
  nwr["landuse"="landfill"](area.sakarya);
  nwr["amenity"="grave_yard"](area.sakarya);
  nwr["landuse"="cemetery"](area.sakarya);
);
out center tags;
"""

# Building footprints across a whole province are a MUCH bigger result set
# than everything else this script pulls (potentially hundreds of
# thousands of ways) - kept as its own query, with its own longer timeout,
# and `out center;` (no tags - FringeContributor only needs building
# locations, not their attributes, so skipping tags meaningfully shrinks
# the response). Split out from OVERPASS_QUERY above so a slow/failed
# building fetch on the public Overpass instance can't take down the
# other, already-reliable layers (highways, stations, etc. still commit
# even if this one fails - see ingest()).
LAND_COVER_OVERPASS_QUERY = f"""
[out:json][timeout:180];
area({SAKARYA_ADMIN_AREA_ID})->.sakarya;
(
  way["building"](area.sakarya);
  way["landuse"~"^(farmland|meadow|grass)$"](area.sakarya);
);
out center;
"""

# Radius for aggregating buildings into a density reading per lattice
# point - chosen so a circle of this radius has the same area as a 1km x
# 1km square (pi*r^2 = 1km^2 => r ~= 564m), matching the production
# heatmap grid's own 1km cell size (see scripts/regenerate_regions.py) so
# the density figure is comparable to "buildings per grid cell".
LAND_COVER_SEARCH_RADIUS_KM = 0.56
LAND_COVER_LATTICE_CELL_SIZE_KM = 1.0

SUPERSEDED_PROJECT_TYPES = ["highway", "railway", "industrial_zone", "port"]
SUPERSEDED_POI_CATEGORIES = [
    "train_station",
    "highway_junction",
    "university",
    "prison",
    "landfill",
    "cemetery",
]


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
    negative_externalities = extract_negative_externalities(elements, CITY)

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
    print(f"Negative externalities (prison/landfill/cemetery): {len(negative_externalities)}")
    for poi in negative_externalities:
        print(f"  - {poi.name} ({poi.category.value})")

    session = SessionLocal()
    try:
        print("\nClearing superseded placeholder data...")
        clear_superseded_placeholder_data(session)

        project_repo = SqlAlchemyProjectRepository(session)
        for project in [*highways, *railways, *industrial, *ports]:
            project_repo.add(project)

        poi_repo = SqlAlchemyPointOfInterestRepository(session)
        for poi in [*stations, *junctions, *universities, *negative_externalities]:
            poi_repo.add(poi)
    finally:
        session.close()

    ingest_land_cover()


def ingest_land_cover() -> None:
    """Building density / open-land ingestion for FringeContributor - split
    into its own function (and its own Overpass query, see
    LAND_COVER_OVERPASS_QUERY) since a province-wide building layer is a
    much larger, slower, more failure-prone fetch than everything else
    ingest() pulls. If this fails (public Overpass instance overload,
    timeout, etc.), the rest of the already-committed data from ingest()
    above is unaffected - the script just reports the failure instead of
    silently producing an empty/stale land-cover layer.
    """
    print("\nQuerying Overpass for Sakarya building/farmland data (this is the slowest layer)...")
    try:
        elements = OverpassClient().query(LAND_COVER_OVERPASS_QUERY, timeout=210)
    except Exception as exc:  # noqa: BLE001 - a failure here must not look like success
        print(f"  FAILED to fetch land cover data ({exc}) - FringeContributor will stay neutral until this succeeds.")
        return
    print(f"  Got {len(elements)} raw building/landuse elements.")

    bbox = CITY_BOUNDING_BOXES[CITY]
    boundary = load_city_boundary(CITY)
    lattice_regions = GridGenerator().generate(bbox, LAND_COVER_LATTICE_CELL_SIZE_KM, boundary=boundary)
    lattice_points = [(region.center_lat, region.center_lon) for region in lattice_regions]
    print(f"  Aggregating onto {len(lattice_points)} lattice points (same grid as the production heatmap)...")

    cells = aggregate_land_cover(elements, lattice_points, CITY, LAND_COVER_SEARCH_RADIUS_KM)
    built_count = sum(1 for c in cells if c.building_count > 0)
    open_count = sum(1 for c in cells if c.is_open_land)
    print(f"  {built_count} lattice points have >=1 building nearby, {open_count} touch open land (farmland/meadow/grass).")

    session = SessionLocal()
    try:
        SqlAlchemyLandCoverRepository(session).bulk_replace(CITY, cells)
    finally:
        session.close()


if __name__ == "__main__":
    ingest()
    print("\nDone.")
