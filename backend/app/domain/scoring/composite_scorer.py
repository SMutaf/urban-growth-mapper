from typing import List

from app.domain.entities.growth_score import GrowthScore
from app.domain.entities.region import Region
from app.domain.scoring.contributors.interfaces import IScoreContributor
from app.domain.scoring.normalization import normalize_scores
from app.domain.scoring.scoring_context import ScoringContext


class CompositeHeatmapScorer:
    """Combines any number of independent IScoreContributor factors into a
    single growth score per region (Open/Closed: adding factors means adding
    contributors to the list passed in - this class itself never changes).
    """

    def __init__(self, contributors: List[IScoreContributor]):
        self._contributors = contributors

    def score_regions(self, regions: List[Region], context: ScoringContext) -> List[GrowthScore]:
        raw_scores = [
            GrowthScore(region_id=region.id, raw_score=self._score_region(region, context))
            for region in regions
        ]
        return normalize_scores(raw_scores)

    def _score_region(self, region: Region, context: ScoringContext) -> float:
        return sum(contributor.contribute(region, context) for contributor in self._contributors)
