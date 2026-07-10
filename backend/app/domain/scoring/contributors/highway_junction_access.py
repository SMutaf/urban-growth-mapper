from app.domain.entities.point_of_interest import POICategory
from app.domain.entities.region import Region
from app.domain.geo_utils import haversine_distance_km
from app.domain.scoring.band_function import banded_value
from app.domain.scoring.scoring_context import ScoringContext

# Literature: distance to the nearest interchange/exit (not the highway
# corridor - see HighwayNoiseContributor) is positive, decaying to nothing
# by ~800m. Immediately at the exit (0-150m) there can be a mild penalty
# from traffic/noise around the ramp itself.
ACCESS_BAND = [(0.0, -0.1), (0.15, 0.0), (0.35, 0.8), (0.8, 0.0)]


class HighwayJunctionAccessContributor:
    def contribute(self, region: Region, context: ScoringContext) -> float:
        junctions = [
            p for p in context.points_of_interest if p.category == POICategory.HIGHWAY_JUNCTION
        ]
        if not junctions:
            return 0.0
        nearest_km = min(
            haversine_distance_km(region.center_lat, region.center_lon, p.latitude, p.longitude)
            for p in junctions
        )
        return banded_value(nearest_km, ACCESS_BAND)
