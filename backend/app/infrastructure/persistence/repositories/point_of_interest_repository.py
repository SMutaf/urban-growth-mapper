from typing import List

from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point
from sqlalchemy.orm import Session

from app.domain.entities.point_of_interest import POICategory, PointOfInterest
from app.domain.entities.project import ProjectStatus
from app.infrastructure.persistence.models import PointOfInterestModel


class SqlAlchemyPointOfInterestRepository:
    """Adapter implementing IPointOfInterestRepository on top of PostGIS."""

    def __init__(self, session: Session):
        self._session = session

    def list_by_city(self, city: str) -> List[PointOfInterest]:
        rows = self._session.query(PointOfInterestModel).filter(
            PointOfInterestModel.city == city
        ).all()
        return [self._to_entity(row) for row in rows]

    def add(self, poi: PointOfInterest) -> PointOfInterest:
        model = self._to_model(poi)
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return self._to_entity(model)

    @staticmethod
    def _to_entity(model: PointOfInterestModel) -> PointOfInterest:
        point = to_shape(model.location)
        return PointOfInterest(
            id=model.id,
            name=model.name,
            category=POICategory(model.category),
            status=ProjectStatus(model.status),
            city=model.city,
            latitude=point.y,
            longitude=point.x,
            importance=model.importance,
        )

    @staticmethod
    def _to_model(poi: PointOfInterest) -> PointOfInterestModel:
        return PointOfInterestModel(
            name=poi.name,
            category=poi.category.value,
            status=poi.status.value,
            city=poi.city,
            importance=poi.importance,
            location=from_shape(Point(poi.longitude, poi.latitude), srid=4326),
        )
