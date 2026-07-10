from app.domain.entities.project import ProjectType
from app.domain.entities.region import Region
from app.domain.geo_utils import haversine_distance_km
from app.domain.scoring.band_function import banded_value
from app.domain.scoring.scoring_context import ScoringContext

# Literature: proximity to the rail corridor itself (not a station) is a
# pure noise/severance disamenity, significant only very close-in (roughly
# 0-200m) and gone by a few hundred metres. Distinct from
# RailStationAccessContributor, which scores distance to the station point
# and is positive at moderate distance - the two effects are independent and
# can both apply to the same region (e.g. right next to the tracks but also
# within the station's peak-value band).
NOISE_BAND = [(0.0, -0.4), (0.2, 0.0)]


class RailwayNoiseContributor:
    def contribute(self, region: Region, context: ScoringContext) -> float:
        railways = [p for p in context.projects if p.project_type == ProjectType.RAILWAY]
        if not railways:
            return 0.0
        nearest_km = min(
            haversine_distance_km(region.center_lat, region.center_lon, p.latitude, p.longitude)
            for p in railways
        )
        return banded_value(nearest_km, NOISE_BAND)
