from typing import List, Optional, Tuple

from geoalchemy2 import Geometry
from geoalchemy2.shape import from_shape
from shapely.geometry import MultiPolygon, Point
from shapely.geometry.base import BaseGeometry
from sqlalchemy import cast, func
from sqlalchemy.orm import Session

from app.infrastructure.persistence.models import DistrictBoundaryModel


class SqlAlchemyDistrictBoundaryRepository:
    """Adapter for district_boundaries on top of PostGIS.

    bulk_insert is an ingestion-only operation (see
    scripts/ingest_sakarya_population.py) and intentionally isn't part of
    IDistrictDemographicsRepository - only find_growth_rate_for_point is,
    since that's the only thing HeatmapService needs.
    """

    def __init__(self, session: Session):
        self._session = session

    def bulk_insert(
        self, city: str, records: List[Tuple[str, float, BaseGeometry]]
    ) -> None:
        models = [
            DistrictBoundaryModel(
                district_name=district_name,
                city=city,
                population_growth_rate=growth_rate,
                boundary=from_shape(self._as_multipolygon(geometry), srid=4326),
            )
            for district_name, growth_rate, geometry in records
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

    @staticmethod
    def _as_multipolygon(geometry: BaseGeometry) -> MultiPolygon:
        if isinstance(geometry, MultiPolygon):
            return geometry
        return MultiPolygon([geometry])
