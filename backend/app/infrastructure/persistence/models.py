from geoalchemy2 import Geometry
from sqlalchemy import Column, Float, Integer, String

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
    city = Column(String, nullable=False, index=True)
    population_growth_rate = Column(Float, nullable=False)
    boundary = Column(Geometry(geometry_type="MULTIPOLYGON", srid=4326), nullable=False)
