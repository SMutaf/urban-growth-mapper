import math
from typing import List, Optional

from app.domain.entities.growth_score import GrowthScore
from app.domain.entities.region import Region
from app.domain.scoring.contributors.interfaces import IScoreContributor
from app.domain.scoring.normalization import normalize_scores
from app.domain.scoring.scoring_context import ScoringContext


class CompositeHeatmapScorer:
    """Combines any number of independent IScoreContributor factors into a
    single growth score per region (Open/Closed: adding factors means adding
    contributors to the list passed in - this class itself never changes).

    Takes the *product* of every contributor's multiplier, not the sum - see
    IScoreContributor for why (compounding effects, matching how hedonic
    literature states its findings as percentages). There's no privileged
    "base" contributor: CBD distance (CityCenterAccessContributor) achieves
    its Alonso-style dominance simply by having a much wider multiplier
    range than the others, not by playing a structurally different role
    here - every contributor is combined the exact same way.

    `weights` (optional, parallel to `contributors`) raises each
    contributor's multiplier to that power before multiplying it in -
    weight 1.0 uses it as-is, 0.0 neutralizes it entirely (x**0 == 1), > 1.0
    amplifies its percentage effect, < 1.0 dampens it. This is how land-use
    profiles (see LandUseProfile / di.py) reweight the same contributors
    differently for residential vs commercial vs industrial scoring without
    needing a different contributor implementation per profile. Omitting
    `weights` (the default) is equivalent to every weight being 1.0 - the
    original, profile-agnostic behavior.
    """

    def __init__(self, contributors: List[IScoreContributor], weights: Optional[List[float]] = None):
        self._contributors = contributors
        self._weights = weights if weights is not None else [1.0] * len(contributors)

    def score_regions(self, regions: List[Region], context: ScoringContext) -> List[GrowthScore]:
        raw_scores = [
            GrowthScore(region_id=region.id, raw_score=self._score_region(region, context))
            for region in regions
        ]
        return normalize_scores(raw_scores)

    def _score_region(self, region: Region, context: ScoringContext) -> float:
        return math.prod(
            contributor.contribute(region, context) ** weight
            for contributor, weight in zip(self._contributors, self._weights)
        )
