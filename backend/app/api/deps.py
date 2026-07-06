from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.services.hazard_zone_service import HazardZoneService
from app.application.services.heatmap_service import HeatmapService
from app.application.services.point_of_interest_service import PointOfInterestService
from app.application.services.project_service import ProjectService
from app.application.services.region_service import RegionService
from app.core.di import (
    build_hazard_zone_service,
    build_heatmap_service,
    build_point_of_interest_service,
    build_project_service,
    build_region_service,
)
from app.infrastructure.persistence.database import get_db


def get_heatmap_service(session: Session = Depends(get_db)) -> HeatmapService:
    return build_heatmap_service(session)


def get_project_service(session: Session = Depends(get_db)) -> ProjectService:
    return build_project_service(session)


def get_region_service(session: Session = Depends(get_db)) -> RegionService:
    return build_region_service(session)


def get_point_of_interest_service(
    session: Session = Depends(get_db),
) -> PointOfInterestService:
    return build_point_of_interest_service(session)


def get_hazard_zone_service(session: Session = Depends(get_db)) -> HazardZoneService:
    return build_hazard_zone_service(session)
