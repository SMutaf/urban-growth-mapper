from app.domain.entities.hazard_zone import HazardType
from app.domain.entities.region import Region
from app.domain.geo_utils import haversine_distance_km
from app.domain.scoring.multiplier_utils import penalty_sum_to_multiplier
from app.domain.scoring.scoring_context import ScoringContext

# Relative severity of each hazard type on land value.
HAZARD_TYPE_WEIGHTS = {
    HazardType.EARTHQUAKE: 1.0,
    HazardType.FLOOD: 0.8,
}

# Worst case (sitting right on top of severe, overlapping hazard zones) is a
# steep -75% multiplier, never 0.0 - see multiplier_utils.penalty_sum_to_multiplier.
MAX_TOTAL_SUM = 3.0
MIN_MULTIPLIER = 0.25


class HazardPenaltyContributor:
    """Negative multiplier: proximity to a hazard zone (earthquake, flood...)
    reduces a region's growth score, scaled by the zone's own risk_level and
    decayed by inverse distance - closer and more severe hazards subtract more.
    """

    def contribute(self, region: Region, context: ScoringContext) -> float:
        total = 0.0
        for hazard in context.hazard_zones:
            distance_km = haversine_distance_km(
                region.center_lat, region.center_lon, hazard.latitude, hazard.longitude
            )
            type_weight = HAZARD_TYPE_WEIGHTS.get(hazard.hazard_type, 0.8)
            total += (type_weight * hazard.risk_level) / (1 + distance_km)
        return penalty_sum_to_multiplier(total, MAX_TOTAL_SUM, MIN_MULTIPLIER)
