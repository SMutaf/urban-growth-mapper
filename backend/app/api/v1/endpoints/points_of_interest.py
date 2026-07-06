from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_point_of_interest_service
from app.application.services.point_of_interest_service import PointOfInterestService
from app.domain.entities.point_of_interest import POICategory, PointOfInterest
from app.domain.entities.project import ProjectStatus

router = APIRouter()


class PointOfInterestCreateRequest(BaseModel):
    name: str
    category: POICategory
    status: ProjectStatus
    city: str
    latitude: float
    longitude: float
    importance: float = 1.0


class PointOfInterestResponse(BaseModel):
    id: int | None
    name: str
    category: POICategory
    status: ProjectStatus
    city: str
    latitude: float
    longitude: float
    importance: float


@router.get("/points-of-interest", response_model=List[PointOfInterestResponse])
def list_points_of_interest(
    city: str, service: PointOfInterestService = Depends(get_point_of_interest_service)
):
    return service.list_points_of_interest(city)


@router.post("/points-of-interest", response_model=PointOfInterestResponse)
def create_point_of_interest(
    payload: PointOfInterestCreateRequest,
    service: PointOfInterestService = Depends(get_point_of_interest_service),
):
    poi = PointOfInterest(id=None, **payload.model_dump())
    return service.add_point_of_interest(poi)
