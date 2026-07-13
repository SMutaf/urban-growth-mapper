from collections import defaultdict
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

# A mahalle with fewer than this many ~1km heatmap grid cells inside it
# gets flagged low_sample=True (see group_scores_by_mahalle) - a single
# cell shouldn't be presented as representing a whole neighbourhood's score
# with the same confidence as one averaged over a dozen cells.
LOW_SAMPLE_CELL_THRESHOLD = 3


@dataclass
class MahalleRecord:
    """One neighbourhood polygon plus its containing district's population
    stats (denormalized - see scripts/ingest_sakarya_population.py).
    """

    district_name: str
    mahalle_name: str
    growth_rate: float
    growth_momentum: float
    population: int
    population_year: int
    geometry: BaseGeometry


@dataclass
class MahalleScoreEntry:
    mahalle_name: str
    # None (not 0.0) when zero heatmap cells fell inside this mahalle -
    # "no data" must never be presented as a real, if low, score.
    avg_score: Optional[float]
    cell_count: int
    low_sample: bool


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
                mahalle_name=record.mahalle_name,
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

    def find_mahalle_names_for_points(self, city: str, points: List[Tuple[float, float]]) -> List[Optional[str]]:
        """Reverse-geocode: which mahalle polygon (if any) contains each
        (lat, lon) - same STRtree point-in-polygon approach as
        find_growth_rates_for_points, returning the mahalle's own name
        (DistrictBoundaryModel.mahalle_name) instead of growth stats. None
        means either the point falls outside every polygon, or the mahalle
        it falls in hasn't had mahalle_name backfilled yet (a re-ingest via
        scripts/ingest_sakarya_population.py is required after this column
        was added - see scripts/init_db.py's migration note).
        """
        rows = (
            self._session.query(DistrictBoundaryModel.boundary, DistrictBoundaryModel.mahalle_name)
            .filter(DistrictBoundaryModel.city == city)
            .all()
        )
        if not rows:
            return [None] * len(points)

        polygons = [to_shape(boundary) for boundary, _ in rows]
        names = [name for _, name in rows]
        tree = STRtree(polygons)

        results: List[Optional[str]] = []
        for lat, lon in points:
            point = Point(lon, lat)
            match = None
            for idx in tree.query(point):
                if polygons[idx].contains(point):
                    match = names[idx]
                    break
            results.append(match)
        return results

    def group_scores_by_mahalle(
        self, city: str, district_name: str, scored_points: List[Tuple[float, float, float]]
    ) -> List[MahalleScoreEntry]:
        """Averages heatmap grid scores per mahalle polygon within one
        district, via the same point-in-polygon technique as
        find_growth_rates_for_points. `scored_points` is (lat, lon, score)
        for the WHOLE city's heatmap grid, not pre-filtered to this
        district - a mahalle's cells can sit right at its edge.

        Every mahalle in the district is included even with zero matched
        cells (avg_score=None then, not a fabricated 0.0) - see
        MahalleScoreEntry and LOW_SAMPLE_CELL_THRESHOLD.
        """
        rows = (
            self._session.query(DistrictBoundaryModel.mahalle_name, DistrictBoundaryModel.boundary)
            .filter(DistrictBoundaryModel.city == city, DistrictBoundaryModel.district_name == district_name)
            .all()
        )
        if not rows:
            return []

        names = [name for name, _ in rows]
        polygons = [to_shape(boundary) for _, boundary in rows]
        tree = STRtree(polygons)

        scores_by_index: Dict[int, List[float]] = defaultdict(list)
        for lat, lon, score in scored_points:
            point = Point(lon, lat)
            for idx in tree.query(point):
                if polygons[idx].contains(point):
                    scores_by_index[idx].append(score)
                    break

        entries = []
        for idx, name in enumerate(names):
            scores = scores_by_index.get(idx, [])
            entries.append(
                MahalleScoreEntry(
                    mahalle_name=name or "(isimsiz mahalle)",
                    avg_score=(sum(scores) / len(scores)) if scores else None,
                    cell_count=len(scores),
                    low_sample=len(scores) < LOW_SAMPLE_CELL_THRESHOLD,
                )
            )
        entries.sort(key=lambda e: (e.avg_score is None, -(e.avg_score or 0.0)))
        return entries

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
