from typing import Any, Dict, List

from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import MultiLineString, mapping
from sqlalchemy.orm import Session

from app.domain.entities.road_geometry import RoadGeometry
from app.infrastructure.persistence.models import RoadGeometryModel


class SqlAlchemyRoadGeometryRepository:
    """Adapter for road_geometries on top of PostGIS - a map-display-only
    dataset (see app/domain/entities/road_geometry.py), so like
    DistrictBoundaryModel it exposes GeoJSON directly rather than routing
    through a domain repository interface.
    """

    def __init__(self, session: Session):
        self._session = session

    def bulk_replace(self, city: str, geometries: List[RoadGeometry]) -> None:
        self._session.query(RoadGeometryModel).filter(RoadGeometryModel.city == city).delete(
            synchronize_session=False
        )
        models = [
            RoadGeometryModel(
                name=geometry.name,
                project_type=geometry.project_type.value,
                city=city,
                geometry=from_shape(self._as_multilinestring(geometry.segments), srid=4326),
            )
            for geometry in geometries
        ]
        self._session.add_all(models)
        self._session.commit()

    def list_by_city_as_geojson_features(self, city: str) -> List[Dict[str, Any]]:
        rows = self._session.query(RoadGeometryModel).filter(RoadGeometryModel.city == city).all()
        return [
            {
                "type": "Feature",
                "properties": {"name": row.name, "project_type": row.project_type},
                "geometry": mapping(to_shape(row.geometry)),
            }
            for row in rows
        ]

    @staticmethod
    def _as_multilinestring(segments: List[List[tuple]]) -> MultiLineString:
        # (lat, lon) -> (lon, lat): shapely/GeoJSON coordinate order.
        return MultiLineString([[(lon, lat) for lat, lon in segment] for segment in segments])
