from typing import Protocol

from app.domain.entities.region import Region
from app.domain.scoring.scoring_context import ScoringContext


class IScoreContributor(Protocol):
    """A single, independent factor in the growth score (Open/Closed: add a
    new factor by adding a new implementation, never by editing an existing
    one or CompositeHeatmapScorer itself).

    contribute() returns a MULTIPLIER, not an additive delta -
    CompositeHeatmapScorer takes the product of every contributor's output,
    not the sum. 1.0 means "no effect either way"; > 1.0 is a positive
    effect (e.g. 1.3 = +30%); a value in (0, 1.0) is a negative effect (e.g.
    0.7 = -30%). This mirrors how hedonic-pricing literature actually states
    its findings ("X raises value 20-40%"), and lets factors compound the
    way market prices actually do (a location that's both near a station
    AND near a university is worth more than either effect added on its
    own would suggest) - a plain sum can't express that interaction.

    A contributor must NEVER return exactly 0.0 or a negative number: a
    single zero would collapse the entire product to zero regardless of how
    good every other factor is, and a negative would flip its sign. Every
    band's worst case should have an explicit floor safely above zero (e.g.
    0.5, not 0.0) - see band_function.banded_value callers for the
    convention. A contributor that found nothing relevant (e.g. no train
    station in range) returns 1.0 (neutral), not 0.0.
    """

    def contribute(self, region: Region, context: ScoringContext) -> float:
        ...
