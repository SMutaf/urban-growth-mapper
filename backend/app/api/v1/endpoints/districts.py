from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_district_service
from app.application.services.district_service import DistrictService

router = APIRouter()


class DistrictResponse(BaseModel):
    name: str
    city: str
    population: int
    population_year: int
    growth_rate: float


@router.get("/districts", response_model=List[DistrictResponse])
def list_districts(city: str, service: DistrictService = Depends(get_district_service)):
    return service.list_districts(city)


@router.get("/districts/{district_name}/boundary")
def get_district_boundary(
    district_name: str, city: str, service: DistrictService = Depends(get_district_service)
) -> Dict[str, Any]:
    geometries = service.get_district_boundary_geojson(city, district_name)
    if not geometries:
        raise HTTPException(
            status_code=404, detail=f"No boundary found for district '{district_name}' in '{city}'"
        )
    return {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "properties": {}, "geometry": geometry} for geometry in geometries],
    }
