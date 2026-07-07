from dataclasses import dataclass
from typing import List, Optional

from app.domain.entities.growth_score import GrowthScore
from app.domain.entities.region import Region
from app.domain.interpretation.interfaces import ILLMInterpreter
from app.domain.repositories.interfaces import (
    IDistrictDemographicsRepository,
    IHazardZoneRepository,
    IPointOfInterestRepository,
    IProjectRepository,
    IRegionRepository,
)
from app.domain.scoring.interfaces import IHeatmapScorer
from app.domain.scoring.scoring_context import ScoringContext


@dataclass
class HeatmapPoint:
    region_id: int
    center_lat: float
    center_lon: float
    score: float


@dataclass
class HeatmapResult:
    points: List[HeatmapPoint]
    interpretation: Optional[str]


class HeatmapService:
    """Orchestrates the 'compute growth heatmap for a city' use case.

    Depends only on abstractions (ports) from the domain layer - concrete
    implementations are injected by the composition root (app/core/di.py).
    """

    def __init__(
        self,
        project_repo: IProjectRepository,
        region_repo: IRegionRepository,
        poi_repo: IPointOfInterestRepository,
        hazard_repo: IHazardZoneRepository,
        district_repo: IDistrictDemographicsRepository,
        scorer: IHeatmapScorer,
        interpreter: ILLMInterpreter,
    ):
        self._project_repo = project_repo
        self._region_repo = region_repo
        self._poi_repo = poi_repo
        self._hazard_repo = hazard_repo
        self._district_repo = district_repo
        self._scorer = scorer
        self._interpreter = interpreter

    def generate_heatmap(self, city: str) -> HeatmapResult:
        regions = self._region_repo.list_by_city(city)
        context = ScoringContext(
            projects=self._project_repo.list_by_city(city),
            points_of_interest=self._poi_repo.list_by_city(city),
            hazard_zones=self._hazard_repo.list_by_city(city),
            region_growth_rates=self._lookup_growth_rates(city, regions),
        )
        scores = self._scorer.score_regions(regions, context)
        score_by_region = self._index_scores(scores)

        points = [
            HeatmapPoint(
                region_id=region.id,
                center_lat=region.center_lat,
                center_lon=region.center_lon,
                score=score_by_region.get(region.id, 0.0),
            )
            for region in regions
        ]
        interpretation = self._interpreter.interpret(scores, context.projects)
        return HeatmapResult(points=points, interpretation=interpretation)

    def _lookup_growth_rates(self, city: str, regions: List[Region]) -> dict:
        rates = {}
        for region in regions:
            rate = self._district_repo.find_growth_rate_for_point(
                city, region.center_lat, region.center_lon
            )
            if rate is not None:
                rates[region.id] = rate
        return rates

    @staticmethod
    def _index_scores(scores: List[GrowthScore]) -> dict:
        return {score.region_id: score.normalized_score for score in scores}
