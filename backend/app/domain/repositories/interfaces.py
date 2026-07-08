from typing import List, Optional, Protocol

from app.domain.entities.district import District
from app.domain.entities.hazard_zone import HazardZone
from app.domain.entities.point_of_interest import PointOfInterest
from app.domain.entities.project import Project
from app.domain.entities.region import Region


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
    def list_by_city(self, city: str) -> List[PointOfInterest]:
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

    def find_growth_rate_for_point(self, city: str, lat: float, lon: float) -> Optional[float]:
        ...

    def list_districts(self, city: str) -> List[District]:
        ...
