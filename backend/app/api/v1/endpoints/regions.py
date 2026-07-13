from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_region_service
from app.application.services.region_service import RegionService
from app.core.city_bounds import CITY_BOUNDING_BOXES, load_city_boundary

router = APIRouter()


class RegionResponse(BaseModel):
    id: int | None
    name: str
    city: str
    center_lat: float
    center_lon: float


@router.get("/regions", response_model=List[RegionResponse])
def list_regions(city: str, service: RegionService = Depends(get_region_service)):
    return service.list_regions(city)


@router.post("/regions/generate", response_model=List[RegionResponse])
def generate_regions(
    city: str,
    cell_size_km: float = 1.0,
    service: RegionService = Depends(get_region_service),
):
    bbox = CITY_BOUNDING_BOXES.get(city.lower())
    if bbox is None:
        raise HTTPException(status_code=404, detail=f"No bounding box configured for city '{city}'")
    boundary = load_city_boundary(city.lower())
    return service.generate_regions(city, bbox, cell_size_km, boundary=boundary)
