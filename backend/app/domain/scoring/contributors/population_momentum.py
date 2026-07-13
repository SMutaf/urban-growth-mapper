from app.domain.entities.region import Region
from app.domain.scoring.scoring_context import ScoringContext

# Observed momentum values (recent-half CAGR minus overall CAGR) across
# Sakarya districts are roughly +/-2%. This scale turns that into a
# meaningful ~+/-15% multiplier swing without letting a single district's
# momentum reading dominate the whole product. Floored well above zero.
POPULATION_MOMENTUM_SCALE = 8.0
MIN_MULTIPLIER = 0.6


class PopulationMomentumContributor:
    """Multiplier based on whether a district's population growth is
    currently accelerating or decelerating (see
    population_xlsx_parser.compute_momentum) - distinct from
    PopulationGrowthContributor, which only sees the long-run average and
    can't tell "was booming, now flat" apart from "just starting to boom".
    A district with the same overall CAGR as another but positive momentum
    is the one actually heating up right now.
    """

    def contribute(self, region: Region, context: ScoringContext) -> float:
        momentum = context.region_growth_momentum.get(region.id)
        if momentum is None:
            return 1.0
        return max(1.0 + momentum * POPULATION_MOMENTUM_SCALE, MIN_MULTIPLIER)
