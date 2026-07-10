from app.domain.entities.point_of_interest import POICategory
from app.domain.entities.region import Region
from app.domain.geo_utils import haversine_distance_km
from app.domain.scoring.band_function import banded_value
from app.domain.scoring.scoring_context import ScoringContext

# Hedonic-pricing literature: an inverted-U relationship with the nearest
# station. Right next to it (0-400m) is a mild disamenity (noise, crowding);
# 400-800m is the peak accessibility premium; it decays through 2.5km and is
# gone beyond that. These are relative-magnitude priors, not calibrated to
# Sakarya - see urban-growth-mapper literature notes.
ACCESS_BAND = [
    (0.0, -0.3),
    (0.35, -0.2),
    (0.4, 0.9),
    (0.8, 1.0),
    (1.5, 0.5),
    (2.5, 0.1),
    (3.0, 0.0),
]


class RailStationAccessContributor:
    def contribute(self, region: Region, context: ScoringContext) -> float:
        stations = [p for p in context.points_of_interest if p.category == POICategory.TRAIN_STATION]
        if not stations:
            return 0.0
        nearest_km = min(
            haversine_distance_km(region.center_lat, region.center_lon, p.latitude, p.longitude)
            for p in stations
        )
        return banded_value(nearest_km, ACCESS_BAND)
