from app.domain.entities.project import ProjectType
from app.domain.entities.region import Region
from app.domain.geo_utils import haversine_distance_km
from app.domain.scoring.band_function import banded_value
from app.domain.scoring.scoring_context import ScoringContext

# Literature: proximity to the motorway/highway corridor itself (not a
# junction/exit) is a noise/severance disamenity, significant only very
# close-in and fading within a couple hundred metres. Distinct from
# HighwayJunctionAccessContributor, which scores distance to the nearest
# interchange and is positive at moderate distance. -30% right on the
# shoulder, neutral by 200m.
NOISE_BAND = [(0.0, 0.7), (0.2, 1.0)]


class HighwayNoiseContributor:
    def contribute(self, region: Region, context: ScoringContext) -> float:
        highways = context.projects_by_type(ProjectType.HIGHWAY)
        if not highways:
            return 1.0
        nearest_km = min(
            haversine_distance_km(region.center_lat, region.center_lon, p.latitude, p.longitude)
            for p in highways
        )
        return banded_value(nearest_km, NOISE_BAND)
