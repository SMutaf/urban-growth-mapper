"""Composition root: the one place concrete infrastructure/domain
implementations are wired to the abstractions the application layer depends on.

To add a real LLM provider later, implement ILLMInterpreter (e.g.
ClaudeLLMInterpreter) and change the single line below that constructs
NullLLMInterpreter - HeatmapService and everything above it stays untouched.
Adding a new scoring factor means adding a new IScoreContributor and
appending it to the CompositeHeatmapScorer list below - the existing
contributors never need to change for that.
"""

from sqlalchemy.orm import Session

from app.application.services.district_service import DistrictService
from app.application.services.hazard_zone_service import HazardZoneService
from app.application.services.heatmap_service import HeatmapService
from app.application.services.point_of_interest_service import PointOfInterestService
from app.application.services.project_service import ProjectService
from app.application.services.region_service import RegionService
from app.domain.grid.grid_generator import GridGenerator
from app.domain.interpretation.null_interpreter import NullLLMInterpreter
from app.domain.scoring.composite_scorer import CompositeHeatmapScorer
from app.domain.scoring.contributors.hazard_penalty import HazardPenaltyContributor
from app.domain.scoring.contributors.highway_junction_access import (
    HighwayJunctionAccessContributor,
)
from app.domain.scoring.contributors.highway_noise import HighwayNoiseContributor
from app.domain.scoring.contributors.industrial_zone_access import (
    IndustrialZoneAccessContributor,
)
from app.domain.scoring.contributors.poi_proximity import PoiProximityContributor
from app.domain.scoring.contributors.population_growth import PopulationGrowthContributor
from app.domain.scoring.contributors.project_proximity import ProjectProximityContributor
from app.domain.scoring.contributors.rail_station_access import RailStationAccessContributor
from app.domain.scoring.contributors.railway_noise import RailwayNoiseContributor
from app.domain.scoring.contributors.university_proximity import UniversityProximityContributor
from app.infrastructure.persistence.repositories.district_boundary_repository import (
    SqlAlchemyDistrictBoundaryRepository,
)
from app.infrastructure.persistence.repositories.hazard_zone_repository import (
    SqlAlchemyHazardZoneRepository,
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


def build_heatmap_service(session: Session) -> HeatmapService:
    return HeatmapService(
        project_repo=SqlAlchemyProjectRepository(session),
        region_repo=SqlAlchemyRegionRepository(session),
        poi_repo=SqlAlchemyPointOfInterestRepository(session),
        hazard_repo=SqlAlchemyHazardZoneRepository(session),
        district_repo=SqlAlchemyDistrictBoundaryRepository(session),
        scorer=CompositeHeatmapScorer(
            [
                ProjectProximityContributor(),
                PoiProximityContributor(),
                HazardPenaltyContributor(),
                PopulationGrowthContributor(),
                RailwayNoiseContributor(),
                RailStationAccessContributor(),
                HighwayNoiseContributor(),
                HighwayJunctionAccessContributor(),
                UniversityProximityContributor(),
                IndustrialZoneAccessContributor(),
            ]
        ),
        interpreter=NullLLMInterpreter(),
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
