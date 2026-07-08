from typing import Any, Dict, List

from app.domain.entities.district import District
from app.infrastructure.persistence.repositories.district_boundary_repository import (
    SqlAlchemyDistrictBoundaryRepository,
)


class DistrictService:
    """Unlike the other application services, this one is typed directly
    against the concrete PostGIS repository rather than a domain interface:
    both of its operations (listing districts, exporting boundary GeoJSON
    for map display) are read/visualization concerns rather than domain use
    cases, so there's no abstraction worth introducing here.
    """

    def __init__(self, district_repo: SqlAlchemyDistrictBoundaryRepository):
        self._district_repo = district_repo

    def list_districts(self, city: str) -> List[District]:
        return self._district_repo.list_districts(city)

    def get_district_boundary_geojson(self, city: str, district_name: str) -> List[Dict[str, Any]]:
        return self._district_repo.get_district_boundary_geojson(city, district_name)
