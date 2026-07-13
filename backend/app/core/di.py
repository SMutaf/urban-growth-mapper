"""Composition root: the one place concrete infrastructure/domain
implementations are wired to the abstractions the application layer depends on.

To add a real LLM provider later, implement ILLMInterpreter (e.g.
ClaudeLLMInterpreter) and change the single line below that constructs
NullLLMInterpreter - HeatmapService and everything above it stays untouched.
Adding a new scoring factor means adding a new IScoreContributor and
appending it to the CompositeHeatmapScorer list below - the existing
contributors never need to change for that.
"""

from typing import Dict, List, Type

from sqlalchemy.orm import Session

from app.application.services.advisory_service import AdvisoryService
from app.application.services.district_service import DistrictService
from app.application.services.hazard_zone_service import HazardZoneService
from app.application.services.heatmap_service import HeatmapService
from app.application.services.mahalle_detail_service import MahalleDetailService
from app.application.services.point_of_interest_service import PointOfInterestService
from app.application.services.project_service import ProjectService
from app.application.services.region_service import RegionService
from app.application.services.road_geometry_service import RoadGeometryService
from app.core.config import get_settings
from app.domain.entities.land_use_profile import LandUseProfile
from app.domain.grid.grid_generator import GridGenerator
from app.domain.interpretation.advisory_interfaces import IAdvisoryLLMClient
from app.domain.interpretation.null_advisory_client import NullAdvisoryLLMClient
from app.domain.interpretation.null_interpreter import NullLLMInterpreter
from app.domain.scoring.composite_scorer import CompositeHeatmapScorer
from app.domain.scoring.contributors.city_center_access import CityCenterAccessContributor
from app.domain.scoring.contributors.growth_direction import GrowthDirectionContributor
from app.domain.scoring.contributors.hazard_penalty import HazardPenaltyContributor
from app.domain.scoring.contributors.highway_junction_access import (
    HighwayJunctionAccessContributor,
)
from app.domain.scoring.contributors.highway_noise import HighwayNoiseContributor
from app.domain.scoring.contributors.industrial_zone_access import (
    IndustrialZoneAccessContributor,
)
from app.domain.scoring.contributors.fringe import FringeContributor
from app.domain.scoring.contributors.interfaces import IScoreContributor
from app.domain.scoring.contributors.negative_externality import NegativeExternalityContributor
from app.domain.scoring.contributors.poi_proximity import PoiProximityContributor
from app.domain.scoring.contributors.population_growth import PopulationGrowthContributor
from app.domain.scoring.contributors.population_momentum import PopulationMomentumContributor
from app.domain.scoring.contributors.project_proximity import ProjectProximityContributor
from app.domain.scoring.contributors.rail_station_access import RailStationAccessContributor
from app.domain.scoring.contributors.railway_noise import RailwayNoiseContributor
from app.domain.scoring.contributors.university_proximity import UniversityProximityContributor
from app.infrastructure.llm.ollama_advisory_client import OllamaAdvisoryClient
from app.infrastructure.persistence.repositories.district_boundary_repository import (
    SqlAlchemyDistrictBoundaryRepository,
)
from app.infrastructure.persistence.repositories.hazard_zone_repository import (
    SqlAlchemyHazardZoneRepository,
)
from app.infrastructure.persistence.repositories.land_cover_repository import (
    SqlAlchemyLandCoverRepository,
)
from app.infrastructure.persistence.repositories.point_of_interest_repository import (
    SqlAlchemyPointOfInterestRepository,
)
from app.infrastructure.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from app.infrastructure.persistence.repositories.region_repository import (
    SqlAlchemyRegionRepository,
)
from app.infrastructure.persistence.repositories.road_geometry_repository import (
    SqlAlchemyRoadGeometryRepository,
)

# Per-profile weight overrides, keyed by contributor class - a contributor
# not listed for a given profile defaults to 1.0 (unweighted, its normal
# behavior). Weight raises the contributor's multiplier to that power (see
# CompositeHeatmapScorer): 0 neutralizes it, >1 amplifies its effect, <1
# dampens it. These are literature-informed priors (Alonso/Von Thünen bid-
# rent curves differing by land use), not calibrated to real Sakarya
# transaction data - same caveat as every other weight in this model.
PROFILE_WEIGHTS: Dict[LandUseProfile, Dict[Type[IScoreContributor], float]] = {
    LandUseProfile.RESIDENTIAL: {
        ProjectProximityContributor: 0.7,
        PoiProximityContributor: 1.3,
        HazardPenaltyContributor: 1.5,
        RailwayNoiseContributor: 1.3,
        RailStationAccessContributor: 1.2,
        HighwayNoiseContributor: 1.3,
        HighwayJunctionAccessContributor: 0.5,
        UniversityProximityContributor: 1.2,
        IndustrialZoneAccessContributor: 0.6,
        NegativeExternalityContributor: 1.4,
        FringeContributor: 1.1,
    },
    LandUseProfile.COMMERCIAL: {
        ProjectProximityContributor: 1.2,
        PoiProximityContributor: 1.1,
        CityCenterAccessContributor: 1.5,
        HazardPenaltyContributor: 0.7,
        PopulationGrowthContributor: 1.2,
        PopulationMomentumContributor: 1.2,
        GrowthDirectionContributor: 1.1,
        RailwayNoiseContributor: 0.6,
        RailStationAccessContributor: 1.3,
        HighwayNoiseContributor: 0.6,
        HighwayJunctionAccessContributor: 1.1,
        UniversityProximityContributor: 1.1,
        IndustrialZoneAccessContributor: 0.8,
        NegativeExternalityContributor: 0.7,
        FringeContributor: 0.8,
    },
    LandUseProfile.INDUSTRIAL: {
        ProjectProximityContributor: 1.3,
        PoiProximityContributor: 0.3,
        CityCenterAccessContributor: 0.4,
        PopulationGrowthContributor: 0.5,
        PopulationMomentumContributor: 0.5,
        GrowthDirectionContributor: 0.6,
        RailwayNoiseContributor: 0.3,
        RailStationAccessContributor: 0.6,
        HighwayNoiseContributor: 0.2,
        HighwayJunctionAccessContributor: 1.6,
        UniversityProximityContributor: 0.3,
        IndustrialZoneAccessContributor: 1.6,
        NegativeExternalityContributor: 0.5,
        FringeContributor: 1.3,
    },
}


def _build_contributors() -> List[IScoreContributor]:
    return [
        ProjectProximityContributor(),
        PoiProximityContributor(),
        CityCenterAccessContributor(),
        HazardPenaltyContributor(),
        PopulationGrowthContributor(),
        PopulationMomentumContributor(),
        GrowthDirectionContributor(),
        RailwayNoiseContributor(),
        RailStationAccessContributor(),
        HighwayNoiseContributor(),
        HighwayJunctionAccessContributor(),
        UniversityProximityContributor(),
        IndustrialZoneAccessContributor(),
        NegativeExternalityContributor(),
        FringeContributor(),
    ]


def _build_scorer(profile: LandUseProfile) -> CompositeHeatmapScorer:
    contributors = _build_contributors()
    if profile == LandUseProfile.BALANCED:
        return CompositeHeatmapScorer(contributors)
    profile_weights = PROFILE_WEIGHTS[profile]
    weights = [profile_weights.get(type(contributor), 1.0) for contributor in contributors]
    return CompositeHeatmapScorer(contributors, weights=weights)


def build_heatmap_service(
    session: Session, profile: LandUseProfile = LandUseProfile.BALANCED
) -> HeatmapService:
    return HeatmapService(
        project_repo=SqlAlchemyProjectRepository(session),
        region_repo=SqlAlchemyRegionRepository(session),
        poi_repo=SqlAlchemyPointOfInterestRepository(session),
        hazard_repo=SqlAlchemyHazardZoneRepository(session),
        district_repo=SqlAlchemyDistrictBoundaryRepository(session),
        land_cover_repo=SqlAlchemyLandCoverRepository(session),
        scorer=_build_scorer(profile),
        interpreter=NullLLMInterpreter(),
    )


def build_advisory_service(session: Session) -> AdvisoryService:
    settings = get_settings()
    llm_client: IAdvisoryLLMClient = (
        OllamaAdvisoryClient(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            temperature=settings.advisory_llm_temperature,
            timeout_seconds=settings.advisory_llm_timeout_seconds,
        )
        if settings.advisory_llm_enabled
        else NullAdvisoryLLMClient()
    )
    return AdvisoryService(
        llm_client=llm_client,
        heatmap_service_factory=lambda profile: build_heatmap_service(session, profile),
        district_repo=SqlAlchemyDistrictBoundaryRepository(session),
    )


def build_project_service(session: Session) -> ProjectService:
    return ProjectService(SqlAlchemyProjectRepository(session))


def build_region_service(session: Session) -> RegionService:
    return RegionService(SqlAlchemyRegionRepository(session), GridGenerator())


def build_point_of_interest_service(session: Session) -> PointOfInterestService:
    return PointOfInterestService(SqlAlchemyPointOfInterestRepository(session))


def build_hazard_zone_service(session: Session) -> HazardZoneService:
    return HazardZoneService(SqlAlchemyHazardZoneRepository(session))


def build_district_service(session: Session) -> DistrictService:
    return DistrictService(SqlAlchemyDistrictBoundaryRepository(session))


def build_mahalle_detail_service(session: Session) -> MahalleDetailService:
    return MahalleDetailService(
        district_repo=SqlAlchemyDistrictBoundaryRepository(session),
        heatmap_service_factory=lambda profile: build_heatmap_service(session, profile),
    )


def build_road_geometry_service(session: Session) -> RoadGeometryService:
    return RoadGeometryService(SqlAlchemyRoadGeometryRepository(session))
