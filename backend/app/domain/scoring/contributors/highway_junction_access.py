from app.domain.entities.point_of_interest import POICategory
from app.domain.entities.region import Region
from app.domain.geo_utils import haversine_distance_km
from app.domain.scoring.band_function import banded_value
from app.domain.scoring.scoring_context import ScoringContext

# Literature ("interchange effect"): the golden zone for commercial
# logistics, warehouses, fuel stations, and retail is roughly 1-5km from the
# nearest interchange/exit (not the highway corridor itself - see
# HighwayNoiseContributor), not the immediate few hundred metres a plain
# reading of "near the highway" might suggest. A parcel that merely *sees*
# the highway from 20km+ from any exit gets no access benefit at all - it
# only picks up HighwayNoiseContributor's disamenity if close enough to the
# corridor, otherwise this contributor is neutral (1.0) for it, same as for
# a parcel far from everything. Immediately at the exit ramp itself
# (0-150m) there's a mild penalty from ramp traffic/noise.
ACCESS_BAND = [(0.0, 0.95), (0.15, 1.0), (1.0, 1.3), (3.0, 1.4), (5.0, 1.15), (8.0, 1.0)]


class HighwayJunctionAccessContributor:
    def contribute(self, region: Region, context: ScoringContext) -> float:
        junctions = context.pois_by_category(POICategory.HIGHWAY_JUNCTION)
        if not junctions:
            return 1.0
        nearest_km = min(
            haversine_distance_km(region.center_lat, region.center_lon, p.latitude, p.longitude)
            for p in junctions
        )
        return banded_value(nearest_km, ACCESS_BAND)
