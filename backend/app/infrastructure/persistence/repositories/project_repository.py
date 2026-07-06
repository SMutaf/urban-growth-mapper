from typing import List

from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point
from sqlalchemy.orm import Session

from app.domain.entities.project import Project, ProjectStatus, ProjectType
from app.infrastructure.persistence.models import ProjectModel


class SqlAlchemyProjectRepository:
    """Adapter implementing IProjectRepository on top of PostGIS."""

    def __init__(self, session: Session):
        self._session = session

    def list_by_city(self, city: str) -> List[Project]:
        rows = self._session.query(ProjectModel).filter(ProjectModel.city == city).all()
        return [self._to_entity(row) for row in rows]

    def add(self, project: Project) -> Project:
        model = self._to_model(project)
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return self._to_entity(model)

    @staticmethod
    def _to_entity(model: ProjectModel) -> Project:
        point = to_shape(model.location)
        return Project(
            id=model.id,
            name=model.name,
            project_type=ProjectType(model.project_type),
            status=ProjectStatus(model.status),
            city=model.city,
            latitude=point.y,
            longitude=point.x,
            importance=model.importance,
            description=model.description,
        )

    @staticmethod
    def _to_model(project: Project) -> ProjectModel:
        return ProjectModel(
            name=project.name,
            project_type=project.project_type.value,
            status=project.status.value,
            city=project.city,
            importance=project.importance,
            description=project.description,
            location=from_shape(Point(project.longitude, project.latitude), srid=4326),
        )
