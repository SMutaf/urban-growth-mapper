from typing import Any, Dict

from fastapi import APIRouter, Depends

from app.api.deps import get_road_geometry_service
from app.application.services.road_geometry_service import RoadGeometryService

router = APIRouter()


@router.get("/road-geometries")
def get_road_geometries(city: str, service: RoadGeometryService = Depends(get_road_geometry_service)) -> Dict[str, Any]:
    return {"type": "FeatureCollection", "features": service.get_road_geometries_geojson(city)}
