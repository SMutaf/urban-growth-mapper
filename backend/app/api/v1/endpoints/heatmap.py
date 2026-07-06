from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from app.api.deps import get_heatmap_service
from app.application.services.heatmap_service import HeatmapService

router = APIRouter()


class HeatmapPointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    region_id: int
    center_lat: float
    center_lon: float
    score: float


class HeatmapResponse(BaseModel):
    city: str
    points: List[HeatmapPointResponse]
    interpretation: Optional[str]


@router.get("/heatmap", response_model=HeatmapResponse)
def get_heatmap(city: str, service: HeatmapService = Depends(get_heatmap_service)):
    result = service.generate_heatmap(city)
    return HeatmapResponse(city=city, points=result.points, interpretation=result.interpretation)
