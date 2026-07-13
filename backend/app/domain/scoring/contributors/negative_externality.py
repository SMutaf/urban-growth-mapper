from app.domain.entities.point_of_interest import POICategory
from app.domain.entities.region import Region
from app.domain.geo_utils import haversine_distance_km
from app.domain.scoring.band_function import banded_value
from app.domain.scoring.scoring_context import ScoringContext

# Hedonic-pricing literature consistently finds LULUs (locally unwanted land
# uses - prisons, landfills, large cemeteries) among the strongest negative
# price effects, typically strong within ~1km and fading out by 3km.
# Prisons/landfills carry a heavier penalty than cemeteries, which are a
# milder, more culturally-variable disamenity.
PRISON_BAND = [(0.0, 0.65), (1.0, 0.8), (3.0, 1.0)]
LANDFILL_BAND = [(0.0, 0.6), (1.0, 0.75), (3.0, 1.0)]
CEMETERY_BAND = [(0.0, 0.85), (1.0, 0.92), (3.0, 1.0)]

CATEGORY_BANDS = {
    POICategory.PRISON: PRISON_BAND,
    POICategory.LANDFILL: LANDFILL_BAND,
    POICategory.CEMETERY: CEMETERY_BAND,
}


class NegativeExternalityContributor:
    """Multiplicative penalty for proximity to a locally-unwanted land use.
    Independent LULU types stack (a region near both a landfill and a
    cemetery gets both penalties), matching how the multiplicative model
    combines every other independent factor.
    """

    def contribute(self, region: Region, context: ScoringContext) -> float:
        multiplier = 1.0
        for category, band in CATEGORY_BANDS.items():
            pois = context.pois_by_category(category)
            if not pois:
                continue
            nearest_km = min(
                haversine_distance_km(region.center_lat, region.center_lon, p.latitude, p.longitude)
                for p in pois
            )
            multiplier *= banded_value(nearest_km, band)
        return multiplier
