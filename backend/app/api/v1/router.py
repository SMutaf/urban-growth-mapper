from fastapi import APIRouter

from app.api.v1.endpoints import (
    districts,
    hazard_zones,
    heatmap,
    points_of_interest,
    projects,
    regions,
)

api_router = APIRouter()
api_router.include_router(projects.router, tags=["projects"])
api_router.include_router(regions.router, tags=["regions"])
api_router.include_router(points_of_interest.router, tags=["points-of-interest"])
api_router.include_router(hazard_zones.router, tags=["hazard-zones"])
api_router.include_router(districts.router, tags=["districts"])
api_router.include_router(heatmap.router, tags=["heatmap"])
