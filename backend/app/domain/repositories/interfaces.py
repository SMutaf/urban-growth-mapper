from dataclasses import dataclass
from typing import List, Optional, Protocol, Tuple

from app.domain.entities.district import District
from app.domain.entities.hazard_zone import HazardZone
from app.domain.entities.land_cover import LandCoverCell
from app.domain.entities.point_of_interest import POICategory, PointOfInterest
from app.domain.entities.project import Project
from app.domain.entities.region import Region


@dataclass
class DistrictGrowthStats:
    growth_rate: float
    growth_momentum: float


class IProjectRepository(Protocol):
    def list_by_city(self, city: str) -> List[Project]:
        ...

    def add(self, project: Project) -> Project:
        ...


class IRegionRepository(Protocol):
    def list_by_city(self, city: str) -> List[Region]:
        ...

    def bulk_create(self, city: str, regions: List[Region]) -> List[Region]:
        ...


class IPointOfInterestRepository(Protocol):
    def list_by_city(
        self, city: str, categories: Optional[List[POICategory]] = None
    ) -> List[PointOfInterest]:
        """`categories=None` returns every category (what scoring needs -
        see HeatmapService._build_context, which never passes this).
        Frontend search/quick-filter requests pass a short category list
        instead, to fetch e.g. schools+hospitals without pulling in the
        2600+ bus stops bundled in the unfiltered response.
        """
        ...

    def add(self, poi: PointOfInterest) -> PointOfInterest:
        ...


class IHazardZoneRepository(Protocol):
    def list_by_city(self, city: str) -> List[HazardZone]:
        ...

    def add(self, hazard_zone: HazardZone) -> HazardZone:
        ...


class IDistrictDemographicsRepository(Protocol):
    """Looks up district population/growth data. Bulk loading the boundary
    polygons themselves is an ingestion-only concern and deliberately not
    part of this domain-facing interface (see
    scripts/ingest_sakarya_population.py).
    """

    def find_growth_rates_for_points(
        self, city: str, points: List[Tuple[float, float]]
    ) -> List[Optional[DistrictGrowthStats]]:
        """Batched point-in-polygon lookup: one DistrictGrowthStats (or None)
        per (lat, lon) in `points`, same order. Batched rather than one point
        at a time because a heatmap request can involve thousands of
        regions - a per-point DB round trip dominates response time at fine
        grid resolutions.
        """
        ...

    def list_districts(self, city: str) -> List[District]:
        ...

    def list_growth_centroids(self, city: str) -> List[Tuple[float, float, float]]:
        """One (lat, lon, growth_rate) per mahalle polygon centroid - the
        raw material for a directional growth analysis (which geographic
        direction from the city center is growing fastest), as distinct
        from find_growth_rates_for_points which answers "what's the growth
        rate at this exact point".
        """
        ...


class ILandCoverRepository(Protocol):
    """Pre-aggregated building-density readings (see
    app/domain/entities/land_cover.py) - bulk_replace rather than add(),
    since ingestion regenerates the whole city's density grid each run
    (same clear-then-bulk-insert idiom as IDistrictDemographicsRepository's
    ingestion path).
    """

    def list_by_city(self, city: str) -> List[LandCoverCell]:
        ...

    def bulk_replace(self, city: str, cells: List[LandCoverCell]) -> None:
        ...
