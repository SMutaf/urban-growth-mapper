from typing import Protocol

from app.domain.entities.region import Region
from app.domain.scoring.scoring_context import ScoringContext


class IScoreContributor(Protocol):
    """A single, independent factor in the growth score (Open/Closed: add a
    new factor by adding a new implementation, never by editing an existing
    one or CompositeHeatmapScorer itself).
    """

    def contribute(self, region: Region, context: ScoringContext) -> float:
        ...
