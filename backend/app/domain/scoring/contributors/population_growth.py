from app.domain.entities.region import Region
from app.domain.scoring.scoring_context import ScoringContext

# Tuning constant to bring a small growth-rate figure (e.g. 0.0117 for a
# ~1.17% annual rate) into a comparable range to the other proximity-based
# contributors (typically 0.1-1.0). Needs calibration against real feedback,
# same as the other contributor weights.
POPULATION_GROWTH_SCALE = 20.0


class PopulationGrowthContributor:
    """Factor based on the population growth rate of the district a region
    falls in: growing districts score higher, shrinking ones score lower.
    Unlike the other contributors, this isn't proximity/distance-based - the
    growth rate per region is precomputed by HeatmapService via a spatial
    (point-in-polygon) lookup and passed in through ScoringContext.
    """

    def contribute(self, region: Region, context: ScoringContext) -> float:
        growth_rate = context.region_growth_rates.get(region.id)
        if growth_rate is None:
            return 0.0
        return growth_rate * POPULATION_GROWTH_SCALE
