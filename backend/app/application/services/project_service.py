from typing import List

from app.domain.entities.project import Project
from app.domain.repositories.interfaces import IProjectRepository


class ProjectService:
    def __init__(self, project_repo: IProjectRepository):
        self._project_repo = project_repo

    def list_projects(self, city: str) -> List[Project]:
        return self._project_repo.list_by_city(city)

    def add_project(self, project: Project) -> Project:
        return self._project_repo.add(project)
