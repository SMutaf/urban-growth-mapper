from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from geoalchemy2 import Geometry
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import MultiPolygon, Point, mapping
from shapely.geometry.base import BaseGeometry
from sqlalchemy import cast, func
from sqlalchemy.orm import Session

from app.domain.entities.district import District
from app.infrastructure.persistence.models import DistrictBoundaryModel


@dataclass
class MahalleRecord:
    """One neighbourhood polygon plus its containing district's population
    stats (denormalized - see scripts/ingest_sakarya_population.py).
    """

    district_name: str
    growth_rate: float
    population: int
    population_year: int
    geometry: BaseGeometry


class SqlAlchemyDistrictBoundaryRepository:
    """Adapter for district_boundaries on top of PostGIS.

    bulk_insert is an ingestion-only operation and intentionally isn't part
    of IDistrictDemographicsRepository - find_growth_rate_for_point and
    list_districts are, since those are what the application layer needs.
    """

    def __init__(self, session: Session):
        self._session = session

    def bulk_insert(self, city: str, records: List[MahalleRecord]) -> None:
        models = [
            DistrictBoundaryModel(
                district_name=record.district_name,
                city=city,
                population_growth_rate=record.growth_rate,
                population=record.population,
                population_year=record.population_year,
                boundary=from_shape(self._as_multipolygon(record.geometry), srid=4326),
            )
            for record in records
        ]
        self._session.add_all(models)
        self._session.commit()

    def find_growth_rate_for_point(self, city: str, lat: float, lon: float) -> Optional[float]:
        point_wkt = from_shape(Point(lon, lat), srid=4326)
        result = (
            self._session.query(DistrictBoundaryModel.population_growth_rate)
            .filter(DistrictBoundaryModel.city == city)
            .filter(func.ST_Contains(DistrictBoundaryModel.boundary, cast(point_wkt, Geometry)))
            .first()
        )
        return result[0] if result else None

    def list_districts(self, city: str) -> List[District]:
        rows = (
            self._session.query(
                DistrictBoundaryModel.district_name,
                DistrictBoundaryModel.population,
                DistrictBoundaryModel.population_year,
                DistrictBoundaryModel.population_growth_rate,
            )
            .filter(DistrictBoundaryModel.city == city)
            .all()
        )
        # Every mahalle row of the same district carries identical
        # population stats (denormalized at ingestion time) - dedupe here
        # rather than with a possibly non-portable DISTINCT ON query.
        by_name: Dict[str, District] = {}
        for name, population, population_year, growth_rate in rows:
            if name not in by_name:
                by_name[name] = District(
                    name=name,
                    city=city,
                    population=population,
                    population_year=population_year,
                    growth_rate=growth_rate,
                )
        return sorted(by_name.values(), key=lambda d: d.name)

    def get_district_boundary_geojson(self, city: str, district_name: str) -> List[Dict[str, Any]]:
        rows = (
            self._session.query(DistrictBoundaryModel.boundary)
            .filter(DistrictBoundaryModel.city == city, DistrictBoundaryModel.district_name == district_name)
            .all()
        )
        return [mapping(to_shape(row[0])) for row in rows]

    @staticmethod
    def _as_multipolygon(geometry: BaseGeometry) -> MultiPolygon:
        if isinstance(geometry, MultiPolygon):
            return geometry
        return MultiPolygon([geometry])
