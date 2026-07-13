from typing import List

from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point
from sqlalchemy.orm import Session

from app.domain.entities.land_cover import LandCoverCell
from app.infrastructure.persistence.models import LandCoverCellModel


class SqlAlchemyLandCoverRepository:
    """Adapter implementing ILandCoverRepository on top of PostGIS."""

    def __init__(self, session: Session):
        self._session = session

    def list_by_city(self, city: str) -> List[LandCoverCell]:
        rows = self._session.query(LandCoverCellModel).filter(LandCoverCellModel.city == city).all()
        return [self._to_entity(row) for row in rows]

    def bulk_replace(self, city: str, cells: List[LandCoverCell]) -> None:
        self._session.query(LandCoverCellModel).filter(LandCoverCellModel.city == city).delete(
            synchronize_session=False
        )
        models = [self._to_model(city, cell) for cell in cells]
        self._session.add_all(models)
        self._session.commit()

    @staticmethod
    def _to_entity(model: LandCoverCellModel) -> LandCoverCell:
        point = to_shape(model.location)
        return LandCoverCell(
            id=model.id,
            city=model.city,
            latitude=point.y,
            longitude=point.x,
            building_count=model.building_count,
            is_open_land=model.is_open_land,
        )

    @staticmethod
    def _to_model(city: str, cell: LandCoverCell) -> LandCoverCellModel:
        return LandCoverCellModel(
            city=city,
            building_count=cell.building_count,
            is_open_land=cell.is_open_land,
            location=from_shape(Point(cell.longitude, cell.latitude), srid=4326),
        )
