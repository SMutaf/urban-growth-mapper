from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_project_service
from app.application.services.project_service import ProjectService
from app.domain.entities.project import Project, ProjectStatus, ProjectType

router = APIRouter()


class ProjectCreateRequest(BaseModel):
    name: str
    project_type: ProjectType
    status: ProjectStatus
    city: str
    latitude: float
    longitude: float
    importance: float = 1.0
    description: str = ""


class ProjectResponse(BaseModel):
    id: int | None
    name: str
    project_type: ProjectType
    status: ProjectStatus
    city: str
    latitude: float
    longitude: float
    importance: float
    description: str


@router.get("/projects", response_model=List[ProjectResponse])
def list_projects(city: str, service: ProjectService = Depends(get_project_service)):
    return service.list_projects(city)


@router.post("/projects", response_model=ProjectResponse)
def create_project(
    payload: ProjectCreateRequest, service: ProjectService = Depends(get_project_service)
):
    project = Project(id=None, **payload.model_dump())
    return service.add_project(project)
