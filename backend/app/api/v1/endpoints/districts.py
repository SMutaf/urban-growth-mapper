from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_district_service, get_mahalle_detail_service
from app.application.services.district_service import DistrictService
from app.application.services.mahalle_detail_service import MahalleDetailService
from app.domain.entities.land_use_profile import LandUseProfile

router = APIRouter()


class DistrictResponse(BaseModel):
    name: str
    city: str
    population: int
    population_year: int
    growth_rate: float


class MahalleScoreResponse(BaseModel):
    mahalle_adi: str
    ortalama_skor: Optional[float]
    hucre_sayisi: int
    dusuk_ornek: bool


class MahalleScoreRankingResponse(BaseModel):
    ilce_adi: str
    mahalleler: List[MahalleScoreResponse]


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


@router.get("/districts/{district_name}/mahalle-scores", response_model=MahalleScoreRankingResponse)
def get_mahalle_score_ranking(
    district_name: str,
    city: str,
    profile: LandUseProfile = LandUseProfile.BALANCED,
    service: MahalleDetailService = Depends(get_mahalle_detail_service),
):
    entries = service.get_mahalle_score_ranking(city, district_name, profile)
    return MahalleScoreRankingResponse(
        ilce_adi=district_name,
        mahalleler=[
            MahalleScoreResponse(
                mahalle_adi=entry.mahalle_name,
                ortalama_skor=round(entry.avg_score, 3) if entry.avg_score is not None else None,
                hucre_sayisi=entry.cell_count,
                dusuk_ornek=entry.low_sample,
            )
            for entry in entries
        ],
    )
