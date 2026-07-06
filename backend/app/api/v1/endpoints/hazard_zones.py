from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_hazard_zone_service
from app.application.services.hazard_zone_service import HazardZoneService
from app.domain.entities.hazard_zone import HazardType, HazardZone

router = APIRouter()


class HazardZoneCreateRequest(BaseModel):
    name: str
    hazard_type: HazardType
    risk_level: float
    city: str
    latitude: float
    longitude: float


class HazardZoneResponse(BaseModel):
    id: int | None
    name: str
    hazard_type: HazardType
    risk_level: float
    city: str
    latitude: float
    longitude: float


@router.get("/hazard-zones", response_model=List[HazardZoneResponse])
def list_hazard_zones(
    city: str, service: HazardZoneService = Depends(get_hazard_zone_service)
):
    return service.list_hazard_zones(city)


@router.post("/hazard-zones", response_model=HazardZoneResponse)
def create_hazard_zone(
    payload: HazardZoneCreateRequest,
    service: HazardZoneService = Depends(get_hazard_zone_service),
):
    hazard_zone = HazardZone(id=None, **payload.model_dump())
    return service.add_hazard_zone(hazard_zone)
