from dataclasses import dataclass
from typing import List, Optional, Tuple

from app.domain.entities.growth_score import GrowthScore
from app.domain.entities.point_of_interest import POICategory, PointOfInterest
from app.domain.entities.region import Region
from app.domain.interpretation.interfaces import ILLMInterpreter
from app.domain.repositories.interfaces import (
    IDistrictDemographicsRepository,
    IHazardZoneRepository,
    ILandCoverRepository,
    IPointOfInterestRepository,
    IProjectRepository,
    IRegionRepository,
)
from app.domain.scoring.contributors.fringe import DENSITY_MAX_MULTIPLIER, DENSITY_MIN_MULTIPLIER
from app.domain.scoring.fringe_density_band import compute_density_band
from app.domain.scoring.growth_direction_analysis import compute_sector_growth
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
        land_cover_repo: ILandCoverRepository,
        scorer: IHeatmapScorer,
        interpreter: ILLMInterpreter,
    ):
        self._project_repo = project_repo
        self._region_repo = region_repo
        self._poi_repo = poi_repo
        self._hazard_repo = hazard_repo
        self._district_repo = district_repo
        self._land_cover_repo = land_cover_repo
        self._scorer = scorer
        self._interpreter = interpreter

    def generate_heatmap(self, city: str) -> HeatmapResult:
        regions = self._region_repo.list_by_city(city)
        context = self._build_context(city, regions)

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

    # Sentinel id for score_point_with_context's ad-hoc region - real
    # persisted regions come from a Postgres SERIAL primary key, which is
    # always >= 1, so this can never collide with a real region.
    _ADVISORY_POINT_REGION_ID = -1

    def score_point_with_context(self, city: str, lat: float, lon: float) -> Tuple[float, ScoringContext]:
        """Scores an arbitrary (lat, lon) - not necessarily one of the
        pre-generated heatmap grid cells - for the advisory chat (see
        application/services/advisory_service.py). Scored ALONGSIDE the
        city's existing region grid rather than alone, so the returned
        score sits on the same normalized 0-1 scale as the live heatmap:
        normalize_scores() (domain/scoring/normalization.py) log-min-maxes
        over whatever batch of regions it's given, so a single-item batch
        would trivially always normalize to 0.0 - there'd be nothing to
        compare it against. This is why this call costs close to a full
        generate_heatmap() (~5s for Sakarya), not a cheap single-point
        lookup - a deliberate accuracy-over-speed tradeoff, not an
        oversight.
        """
        regions = self._region_repo.list_by_city(city)
        context = self._build_context(city, regions)

        user_point_region = Region(
            id=self._ADVISORY_POINT_REGION_ID, name="advisory-point", city=city,
            center_lat=lat, center_lon=lon,
        )
        scores = self._scorer.score_regions([*regions, user_point_region], context)
        score_by_region = self._index_scores(scores)
        return score_by_region.get(self._ADVISORY_POINT_REGION_ID, 0.0), context

    def _build_context(self, city: str, regions: List[Region]) -> ScoringContext:
        points_of_interest = self._poi_repo.list_by_city(city)
        growth_rates, growth_momentum = self._lookup_district_stats(city, regions)
        land_cover_cells = self._land_cover_repo.list_by_city(city)

        return ScoringContext(
            projects=self._project_repo.list_by_city(city),
            points_of_interest=points_of_interest,
            hazard_zones=self._hazard_repo.list_by_city(city),
            region_growth_rates=growth_rates,
            region_growth_momentum=growth_momentum,
            growth_direction_sectors=self._compute_growth_direction_sectors(city, points_of_interest),
            land_cover_cells=land_cover_cells,
            fringe_density_band=compute_density_band(
                [c.building_count for c in land_cover_cells], DENSITY_MIN_MULTIPLIER, DENSITY_MAX_MULTIPLIER
            ),
        )

    def _lookup_district_stats(
        self, city: str, regions: List[Region]
    ) -> Tuple[dict, dict]:
        points = [(region.center_lat, region.center_lon) for region in regions]
        found_stats = self._district_repo.find_growth_rates_for_points(city, points)
        growth_rates = {}
        growth_momentum = {}
        for region, stats in zip(regions, found_stats):
            if stats is not None:
                growth_rates[region.id] = stats.growth_rate
                growth_momentum[region.id] = stats.growth_momentum
        return growth_rates, growth_momentum

    def _compute_growth_direction_sectors(
        self, city: str, points_of_interest: List[PointOfInterest]
    ) -> List[float]:
        city_centers = [p for p in points_of_interest if p.category == POICategory.CITY_CENTER]
        if not city_centers:
            return []
        center = city_centers[0]
        centroids = self._district_repo.list_growth_centroids(city)
        return compute_sector_growth(centroids, center.latitude, center.longitude)

    @staticmethod
    def _index_scores(scores: List[GrowthScore]) -> dict:
        return {score.region_id: score.normalized_score for score in scores}
