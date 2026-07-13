from typing import Any, Dict, List

from app.infrastructure.persistence.repositories.road_geometry_repository import (
    SqlAlchemyRoadGeometryRepository,
)


class RoadGeometryService:
    """Typed directly against the concrete PostGIS repository, same
    reasoning as DistrictService: this is a read/visualization concern
    (exporting road-line GeoJSON for map display), not a domain use case,
    so there's no abstraction worth introducing.
    """

    def __init__(self, road_geometry_repo: SqlAlchemyRoadGeometryRepository):
        self._road_geometry_repo = road_geometry_repo

    def get_road_geometries_geojson(self, city: str) -> List[Dict[str, Any]]:
        return self._road_geometry_repo.list_by_city_as_geojson_features(city)
