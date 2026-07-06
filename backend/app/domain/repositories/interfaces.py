from typing import List, Protocol

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
