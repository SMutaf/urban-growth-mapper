from app.domain.entities.point_of_interest import POICategory
from app.domain.entities.region import Region
from app.domain.geo_utils import haversine_distance_km
from app.domain.scoring.band_function import banded_value
from app.domain.scoring.scoring_context import ScoringContext

# Alonso (1964) bid-rent theory: distance to the CBD is *the* dominant
# driver of urban land value, not one amenity among many - previously this
# lived inside PoiProximityContributor with the same weight class as a
# hospital or shopping center (0.8, capped at 7km), which badly understates
# its theoretical importance and cuts it off well within Sakarya's actual
# urban extent. A monotonic, convex decline (steep initial drop, flattening
# out) covering the whole mapped province, not an inverted-U like the
# station/junction contributors - classic bid-rent theory has no "too close
# to the CBD" penalty for a generic score (unlike a single land use such as
# purely residential, which can show a mild too-close effect).
#
# There's no privileged "base value" role in CompositeHeatmapScorer (see
# composite_scorer.py) - every contributor's output is just multiplied
# together the same way. This contributor achieves Alonso's claimed CBD
# dominance purely through having a *far wider* multiplier range (0.5x to
# 3.0x - a 6x swing) than any other single contributor, with 1.0 (neutral)
# anchored around 10km, a typical edge-of-urban-core distance in Sakarya.
CBD_ACCESS_BAND = [(0.0, 3.0), (5.0, 1.8), (10.0, 1.0), (20.0, 0.7), (30.0, 0.5)]


class CityCenterAccessContributor:
    def contribute(self, region: Region, context: ScoringContext) -> float:
        centers = context.pois_by_category(POICategory.CITY_CENTER)
        if not centers:
            return 1.0
        nearest_km = min(
            haversine_distance_km(region.center_lat, region.center_lon, p.latitude, p.longitude)
            for p in centers
        )
        return banded_value(nearest_km, CBD_ACCESS_BAND)
