from typing import List

from app.domain.entities.point_of_interest import PointOfInterest
from app.domain.repositories.interfaces import IPointOfInterestRepository


class PointOfInterestService:
    def __init__(self, poi_repo: IPointOfInterestRepository):
        self._poi_repo = poi_repo

    def list_points_of_interest(self, city: str) -> List[PointOfInterest]:
        return self._poi_repo.list_by_city(city)

    def add_point_of_interest(self, poi: PointOfInterest) -> PointOfInterest:
        return self._poi_repo.add(poi)
