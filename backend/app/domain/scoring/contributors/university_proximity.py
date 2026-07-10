from app.domain.entities.point_of_interest import POICategory
from app.domain.entities.region import Region
from app.domain.geo_utils import haversine_distance_km
from app.domain.scoring.band_function import banded_value
from app.domain.scoring.scoring_context import ScoringContext

# Literature: strong, reliable positive effect (student housing demand,
# rental yield, services) - intense within ~1.5km, meaningful but declining
# out to ~5km, negligible beyond.
PROXIMITY_BAND = [(0.0, 1.0), (1.5, 0.8), (5.0, 0.15), (6.0, 0.0)]


class UniversityProximityContributor:
    def contribute(self, region: Region, context: ScoringContext) -> float:
        universities = [
            p for p in context.points_of_interest if p.category == POICategory.UNIVERSITY
        ]
        if not universities:
            return 0.0
        nearest_km = min(
            haversine_distance_km(region.center_lat, region.center_lon, p.latitude, p.longitude)
            for p in universities
        )
        return banded_value(nearest_km, PROXIMITY_BAND)
