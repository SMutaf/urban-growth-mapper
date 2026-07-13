from geoalchemy2 import Geometry
from sqlalchemy import Boolean, Column, Float, Integer, String

from app.infrastructure.persistence.database import Base


class ProjectModel(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    project_type = Column(String, nullable=False)
    status = Column(String, nullable=False)
    city = Column(String, nullable=False, index=True)
    importance = Column(Float, nullable=False, default=1.0)
    description = Column(String, nullable=False, default="")
    location = Column(Geometry(geometry_type="POINT", srid=4326), nullable=False)


class RegionModel(Base):
    __tablename__ = "regions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    city = Column(String, nullable=False, index=True)
    center = Column(Geometry(geometry_type="POINT", srid=4326), nullable=False)


class PointOfInterestModel(Base):
    __tablename__ = "points_of_interest"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    status = Column(String, nullable=False)
    city = Column(String, nullable=False, index=True)
    importance = Column(Float, nullable=False, default=1.0)
    location = Column(Geometry(geometry_type="POINT", srid=4326), nullable=False)


class HazardZoneModel(Base):
    __tablename__ = "hazard_zones"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    hazard_type = Column(String, nullable=False)
    risk_level = Column(Float, nullable=False)
    city = Column(String, nullable=False, index=True)
    location = Column(Geometry(geometry_type="POINT", srid=4326), nullable=False)


class DistrictBoundaryModel(Base):
    """One row per neighborhood (mahalle) polygon, carrying its containing
    district's population growth rate (denormalized at ingestion time -
    see scripts/ingest_sakarya_population.py). We store per-mahalle polygons
    rather than a unioned per-ilce polygon because that's the granularity
    the source boundary file provides.
    """

    __tablename__ = "district_boundaries"

    id = Column(Integer, primary_key=True, index=True)
    district_name = Column(String, nullable=False, index=True)
    # The mahalle's own name (source GeoJSON's "ad" property, see
    # mahalle_geojson_parser.MahalleBoundary.name) - nullable because rows
    # ingested before this column existed won't have it until a re-ingest
    # backfills every row (ingest_sakarya_population.py does a full
    # clear+reinsert, not an in-place update).
    mahalle_name = Column(String, nullable=True, index=True)
    city = Column(String, nullable=False, index=True)
    population_growth_rate = Column(Float, nullable=False)
    population_growth_momentum = Column(Float, nullable=False, default=0.0)
    population = Column(Integer, nullable=False)
    population_year = Column(Integer, nullable=False)
    boundary = Column(Geometry(geometry_type="MULTIPOLYGON", srid=4326), nullable=False)


class RoadGeometryModel(Base):
    """The real line shape of a named highway/railway - map display only,
    see app/domain/entities/road_geometry.py for why this is a separate
    table from `projects` rather than adding a geometry column there.
    Populated by scripts/ingest_sakarya_road_geometries.py.
    """

    __tablename__ = "road_geometries"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    project_type = Column(String, nullable=False)
    city = Column(String, nullable=False, index=True)
    geometry = Column(Geometry(geometry_type="MULTILINESTRING", srid=4326), nullable=False)


class LandCoverCellModel(Base):
    """One pre-aggregated building-density reading on a coarse (~1km) grid
    - see app/domain/entities/land_cover.py for why this isn't one row per
    OSM building. Populated by scripts/ingest_sakarya_osm.py; used by
    FringeContributor (app/domain/scoring/contributors/fringe.py).
    """

    __tablename__ = "land_cover_cells"

    id = Column(Integer, primary_key=True, index=True)
    city = Column(String, nullable=False, index=True)
    building_count = Column(Integer, nullable=False)
    is_open_land = Column(Boolean, nullable=False, default=False)
    location = Column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
