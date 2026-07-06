from typing import List

from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point
from sqlalchemy.orm import Session

from app.domain.entities.region import Region
from app.infrastructure.persistence.models import RegionModel


class SqlAlchemyRegionRepository:
    """Adapter implementing IRegionRepository on top of PostGIS."""

    def __init__(self, session: Session):
        self._session = session

    def list_by_city(self, city: str) -> List[Region]:
        rows = self._session.query(RegionModel).filter(RegionModel.city == city).all()
        return [self._to_entity(row) for row in rows]

    def bulk_create(self, city: str, regions: List[Region]) -> List[Region]:
        models = [self._to_model(city, region) for region in regions]
        self._session.add_all(models)
        self._session.commit()
        for model in models:
            self._session.refresh(model)
        return [self._to_entity(model) for model in models]

    @staticmethod
    def _to_entity(model: RegionModel) -> Region:
        point = to_shape(model.center)
        return Region(
            id=model.id,
            name=model.name,
            city=model.city,
            center_lat=point.y,
            center_lon=point.x,
        )

    @staticmethod
    def _to_model(city: str, region: Region) -> RegionModel:
        return RegionModel(
            name=region.name,
            city=city,
            center=from_shape(Point(region.center_lon, region.center_lat), srid=4326),
        )
