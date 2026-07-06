from app.domain.entities.point_of_interest import POICategory
from app.domain.entities.region import Region
from app.domain.geo_utils import haversine_distance_km
from app.domain.scoring.scoring_context import ScoringContext
from app.domain.scoring.status_weights import STATUS_MULTIPLIERS

# Relative importance of each amenity category. A metro/bus stop shapes daily
# commute patterns the most; a school affects a narrower audience.
POI_CATEGORY_WEIGHTS = {
    POICategory.METRO_STATION: 1.0,
    POICategory.CITY_CENTER: 0.8,
    POICategory.HOSPITAL: 0.7,
    POICategory.SHOPPING_CENTER: 0.6,
    POICategory.BUS_STOP: 0.5,
    POICategory.SCHOOL: 0.5,
    POICategory.OTHER: 0.4,
}


class PoiProximityContributor:
    """Positive factor: sum of every amenity's (category weight x status
    weight x importance), decayed by inverse distance - mirrors
    ProjectProximityContributor but for local amenities rather than
    large regional infrastructure.
    """

    def contribute(self, region: Region, context: ScoringContext) -> float:
        total = 0.0
        for poi in context.points_of_interest:
            distance_km = haversine_distance_km(
                region.center_lat, region.center_lon, poi.latitude, poi.longitude
            )
            category_weight = POI_CATEGORY_WEIGHTS.get(poi.category, 0.4)
            status_weight = STATUS_MULTIPLIERS.get(poi.status, 0.6)
            total += (category_weight * status_weight * poi.importance) / (1 + distance_km)
        return total
