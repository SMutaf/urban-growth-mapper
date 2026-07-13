from app.domain.entities.region import Region
from app.domain.scoring.scoring_context import ScoringContext

# Real Sakarya district CAGRs observed range roughly 0.1%-6.4%/yr. This
# scale turns that into a +/-30%-ish multiplier swing (e.g. Ferizli's 6.4%
# -> +32%) - a meaningfully large but not model-dominating effect, in the
# same influence class as the accessibility contributors rather than the
# CBD contributor's deliberately wider range. Floored well above zero so a
# sharply shrinking district can never flip the sign of the whole product.
POPULATION_GROWTH_SCALE = 5.0
MIN_MULTIPLIER = 0.5


class PopulationGrowthContributor:
    """Multiplier based on the population growth rate of the district a
    region falls in: growing districts score higher, shrinking ones lower.
    Unlike the other contributors, this isn't proximity/distance-based - the
    growth rate per region is precomputed by HeatmapService via a spatial
    (point-in-polygon) lookup and passed in through ScoringContext.
    """

    def contribute(self, region: Region, context: ScoringContext) -> float:
        growth_rate = context.region_growth_rates.get(region.id)
        if growth_rate is None:
            return 1.0
        return max(1.0 + growth_rate * POPULATION_GROWTH_SCALE, MIN_MULTIPLIER)
