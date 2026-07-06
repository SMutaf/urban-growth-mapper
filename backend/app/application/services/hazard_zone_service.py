from typing import List

from app.domain.entities.hazard_zone import HazardZone
from app.domain.repositories.interfaces import IHazardZoneRepository


class HazardZoneService:
    def __init__(self, hazard_repo: IHazardZoneRepository):
        self._hazard_repo = hazard_repo

    def list_hazard_zones(self, city: str) -> List[HazardZone]:
        return self._hazard_repo.list_by_city(city)

    def add_hazard_zone(self, hazard_zone: HazardZone) -> HazardZone:
        return self._hazard_repo.add(hazard_zone)
