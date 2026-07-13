from app.domain.entities.project import ProjectType
from app.domain.entities.region import Region
from app.domain.geo_utils import haversine_distance_km
from app.domain.scoring.band_function import banded_value
from app.domain.scoring.scoring_context import ScoringContext

# Literature: two opposing effects bundled into one distance curve (we don't
# model land-use intent, i.e. whether a region is destined for industrial or
# residential use, so this represents the residential-adjacent case, which
# the literature says dominates very close in): immediately adjacent
# (0-500m) is a mild net negative (noise/pollution cost for nearby housing);
# the real value driver is the 2-8km commutershed, where employment access
# raises housing demand without the direct nuisance cost.
ACCESS_BAND = [(0.0, 0.9), (0.5, 1.0), (2.0, 1.25), (8.0, 1.1), (10.0, 1.0)]


class IndustrialZoneAccessContributor:
    def contribute(self, region: Region, context: ScoringContext) -> float:
        zones = context.projects_by_type(ProjectType.INDUSTRIAL_ZONE)
        if not zones:
            return 1.0
        nearest_km = min(
            haversine_distance_km(region.center_lat, region.center_lon, p.latitude, p.longitude)
            for p in zones
        )
        return banded_value(nearest_km, ACCESS_BAND)
