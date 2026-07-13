from app.domain.entities.point_of_interest import POICategory
from app.domain.entities.region import Region
from app.domain.geo_utils import haversine_distance_km, is_definitely_beyond
from app.domain.scoring.multiplier_utils import positive_sum_to_multiplier
from app.domain.scoring.scoring_context import ScoringContext
from app.domain.scoring.status_weights import STATUS_MULTIPLIERS

# Beyond this, 1/(1+distance_km) is already under ~0.09 - negligible next to
# the weights involved, and small enough relative to the scored area
# (Sakarya's mapped bbox is ~22x19km) to actually narrow down which of the
# thousands of POIs need a real distance check for a given region, which is
# what keeps this contributor affordable at a fine grid resolution.
MAX_RELEVANT_KM = 7.0

# This contributor sums over every nearby amenity with no upper bound, so in
# a dense area (thousands of bus stops within range) its raw total can reach
# the double digits. MAX_TOTAL_SUM caps that raw sum before squashing it into
# a multiplier; MAX_MULTIPLIER is the richest-possible-amenity-mix ceiling
# (+70%) - generous since this contributor represents a whole bundle of
# amenities at once, not a single factor.
MAX_TOTAL_SUM = 3.0
MAX_MULTIPLIER = 1.7

# Relative importance of each amenity category. A metro/bus stop shapes daily
# commute patterns the most; a school affects a narrower audience.
#
# TRAIN_STATION, HIGHWAY_JUNCTION, and UNIVERSITY are deliberately excluded -
# the hedonic-pricing literature calls for banded, non-monotonic distance
# curves for those (see RailStationAccessContributor,
# HighwayJunctionAccessContributor, UniversityProximityContributor), which
# this contributor's plain inverse-distance-decay can't express. Including
# them here too would double-count the same underlying PointOfInterest rows.
#
# CITY_CENTER is also excluded - Alonso (1964) bid-rent theory treats CBD
# distance as the dominant driver of urban land value, not one amenity among
# equals, so it has its own contributor (CityCenterAccessContributor) with a
# far wider radius and its own weight class instead of competing for a share
# of this contributor's amenity cap.
POI_CATEGORY_WEIGHTS = {
    POICategory.METRO_STATION: 1.0,
    POICategory.HOSPITAL: 0.7,
    POICategory.SHOPPING_CENTER: 0.6,
    POICategory.BUS_STOP: 0.5,
    POICategory.SCHOOL: 0.5,
    POICategory.OTHER: 0.4,
}


class PoiProximityContributor:
    """Positive multiplier built from every nearby amenity's (category
    weight x status weight x importance), decayed by inverse distance and
    summed - mirrors ProjectProximityContributor but for local amenities
    rather than large regional infrastructure. The sum is squashed into a
    multiplier at the end (see multiplier_utils) since a contributor must
    return a bounded multiplier, not an unbounded raw sum.
    """

    def contribute(self, region: Region, context: ScoringContext) -> float:
        total = 0.0
        candidates = context.pois_near(region.center_lat, region.center_lon, MAX_RELEVANT_KM)
        for poi in candidates:
            if poi.category not in POI_CATEGORY_WEIGHTS:
                continue
            if is_definitely_beyond(
                region.center_lat, region.center_lon, poi.latitude, poi.longitude, MAX_RELEVANT_KM
            ):
                continue
            distance_km = haversine_distance_km(
                region.center_lat, region.center_lon, poi.latitude, poi.longitude
            )
            category_weight = POI_CATEGORY_WEIGHTS[poi.category]
            status_weight = STATUS_MULTIPLIERS.get(poi.status, 0.6)
            total += (category_weight * status_weight * poi.importance) / (1 + distance_km)
        return positive_sum_to_multiplier(total, MAX_TOTAL_SUM, MAX_MULTIPLIER)
