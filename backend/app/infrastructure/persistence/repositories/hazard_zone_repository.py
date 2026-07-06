from typing import List

from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point
from sqlalchemy.orm import Session

from app.domain.entities.hazard_zone import HazardType, HazardZone
from app.infrastructure.persistence.models import HazardZoneModel


class SqlAlchemyHazardZoneRepository:
    """Adapter implementing IHazardZoneRepository on top of PostGIS."""

    def __init__(self, session: Session):
        self._session = session

    def list_by_city(self, city: str) -> List[HazardZone]:
        rows = self._session.query(HazardZoneModel).filter(HazardZoneModel.city == city).all()
        return [self._to_entity(row) for row in rows]

    def add(self, hazard_zone: HazardZone) -> HazardZone:
        model = self._to_model(hazard_zone)
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return self._to_entity(model)

    @staticmethod
    def _to_entity(model: HazardZoneModel) -> HazardZone:
        point = to_shape(model.location)
        return HazardZone(
            id=model.id,
            name=model.name,
            hazard_type=HazardType(model.hazard_type),
            risk_level=model.risk_level,
            city=model.city,
            latitude=point.y,
            longitude=point.x,
        )

    @staticmethod
    def _to_model(hazard_zone: HazardZone) -> HazardZoneModel:
        return HazardZoneModel(
            name=hazard_zone.name,
            hazard_type=hazard_zone.hazard_type.value,
            risk_level=hazard_zone.risk_level,
            city=hazard_zone.city,
            location=from_shape(Point(hazard_zone.longitude, hazard_zone.latitude), srid=4326),
        )
