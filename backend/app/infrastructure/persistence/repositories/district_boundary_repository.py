from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import MultiPolygon, Point, mapping
from shapely.geometry.base import BaseGeometry
from shapely.strtree import STRtree
from sqlalchemy.orm import Session

from app.domain.entities.district import District
from app.domain.repositories.interfaces import DistrictGrowthStats
from app.infrastructure.persistence.models import DistrictBoundaryModel


@dataclass
class MahalleRecord:
    """One neighbourhood polygon plus its containing district's population
    stats (denormalized - see scripts/ingest_sakarya_population.py).
    """

    district_name: str
    growth_rate: float
    growth_momentum: float
    population: int
    population_year: int
    geometry: BaseGeometry


class SqlAlchemyDistrictBoundaryRepository:
    """Adapter for district_boundaries on top of PostGIS.

    bulk_insert is an ingestion-only operation and intentionally isn't part
    of IDistrictDemographicsRepository - find_growth_rates_for_points and
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
                population_growth_momentum=record.growth_momentum,
                population=record.population,
                population_year=record.population_year,
                boundary=from_shape(self._as_multipolygon(record.geometry), srid=4326),
            )
            for record in records
        ]
        self._session.add_all(models)
        self._session.commit()

    def clear_city(self, city: str) -> None:
        self._session.query(DistrictBoundaryModel).filter(
            DistrictBoundaryModel.city == city
        ).delete(synchronize_session=False)
        self._session.commit()

    def find_growth_rates_for_points(
        self, city: str, points: List[Tuple[float, float]]
    ) -> List[Optional[DistrictGrowthStats]]:
        rows = (
            self._session.query(
                DistrictBoundaryModel.boundary,
                DistrictBoundaryModel.population_growth_rate,
                DistrictBoundaryModel.population_growth_momentum,
            )
            .filter(DistrictBoundaryModel.city == city)
            .all()
        )
        if not rows:
            return [None] * len(points)

        polygons = [to_shape(boundary) for boundary, _, _ in rows]
        stats = [DistrictGrowthStats(growth_rate=rate, growth_momentum=momentum) for _, rate, momentum in rows]
        tree = STRtree(polygons)

        results: List[Optional[DistrictGrowthStats]] = []
        for lat, lon in points:
            point = Point(lon, lat)
            match = None
            for idx in tree.query(point):
                if polygons[idx].contains(point):
                    match = stats[idx]
                    break
            results.append(match)
        return results

    def list_growth_centroids(self, city: str) -> List[Tuple[float, float, float]]:
        rows = (
            self._session.query(
                DistrictBoundaryModel.boundary, DistrictBoundaryModel.population_growth_rate
            )
            .filter(DistrictBoundaryModel.city == city)
            .all()
        )
        centroids = []
        for boundary, growth_rate in rows:
            centroid = to_shape(boundary).centroid
            centroids.append((centroid.y, centroid.x, growth_rate))
        return centroids

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
