from typing import List, Optional

from app.domain.entities.point_of_interest import POICategory, PointOfInterest
from app.domain.repositories.interfaces import IPointOfInterestRepository


class PointOfInterestService:
    def __init__(self, poi_repo: IPointOfInterestRepository):
        self._poi_repo = poi_repo

    def list_points_of_interest(
        self, city: str, categories: Optional[List[POICategory]] = None
    ) -> List[PointOfInterest]:
        return self._poi_repo.list_by_city(city, categories)

    def add_point_of_interest(self, poi: PointOfInterest) -> PointOfInterest:
        return self._poi_repo.add(poi)
