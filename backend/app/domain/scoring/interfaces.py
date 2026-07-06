from typing import List, Protocol

from app.domain.entities.growth_score import GrowthScore
from app.domain.entities.region import Region
from app.domain.scoring.scoring_context import ScoringContext


class IHeatmapScorer(Protocol):
    """Port for turning (regions, context) into a growth score per region.

    Any implementation must be swappable without touching callers (Open/Closed +
    Dependency Inversion) - e.g. a future ML-based scorer could replace the
    composite rule-based one below without changing HeatmapService.
    """

    def score_regions(self, regions: List[Region], context: ScoringContext) -> List[GrowthScore]:
        ...
