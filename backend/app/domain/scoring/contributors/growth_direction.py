from app.domain.entities.point_of_interest import POICategory
from app.domain.entities.region import Region
from app.domain.scoring.growth_direction_analysis import bearing_degrees, sector_value_at_bearing
from app.domain.scoring.scoring_context import ScoringContext

# Same order of magnitude as the population growth/momentum scales - all
# three are CAGR-derived percentages multiplied into the same composite
# score (see composite_scorer.py).
GROWTH_DIRECTION_SCALE = 8.0
MIN_MULTIPLIER = 0.6


class GrowthDirectionContributor:
    """Rewards regions that lie in the compass direction the city is
    actually expanding towards (see domain/scoring/growth_direction_analysis.py),
    on top of - not instead of - the local accessibility/amenity factors.
    Two regions equidistant from downtown but on opposite sides of the city
    can have very different growth trajectories; this is the only
    contributor that can tell them apart.

    Needs a city-center reference point, sourced from the CITY_CENTER POI
    category (already seeded/ingested for CityCenterAccessContributor)
    rather than a hardcoded coordinate, so this stays a general contributor
    rather than one hardwired to Sakarya's geometry.
    """

    def contribute(self, region: Region, context: ScoringContext) -> float:
        if not context.growth_direction_sectors:
            return 1.0
        centers = context.pois_by_category(POICategory.CITY_CENTER)
        if not centers:
            return 1.0
        center = centers[0]

        bearing = bearing_degrees(center.latitude, center.longitude, region.center_lat, region.center_lon)
        sector_value = sector_value_at_bearing(context.growth_direction_sectors, bearing)
        return max(1.0 + sector_value * GROWTH_DIRECTION_SCALE, MIN_MULTIPLIER)
