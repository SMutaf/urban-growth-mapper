from app.domain.entities.point_of_interest import POICategory, PointOfInterest
from app.domain.entities.project import ProjectStatus
from app.domain.entities.region import Region
from app.domain.scoring.contributors.growth_direction import GrowthDirectionContributor
from app.domain.scoring.scoring_context import ScoringContext

CITY_CENTER = PointOfInterest(
    id=1, name="center", category=POICategory.CITY_CENTER, status=ProjectStatus.COMPLETED,
    city="sakarya", latitude=40.0, longitude=30.0,
)

# 8 sectors, index 0 = north, growing at +2 relative to city average; index
# 4 = south, at -2.
SECTORS = [2.0, 0.0, 0.0, 0.0, -2.0, 0.0, 0.0, 0.0]


def test_region_in_favoured_direction_scores_higher_than_disfavoured():
    contributor = GrowthDirectionContributor()
    context = ScoringContext(points_of_interest=[CITY_CENTER], growth_direction_sectors=SECTORS)

    north_region = Region(id=1, name="r", city="sakarya", center_lat=40.5, center_lon=30.0)
    south_region = Region(id=2, name="r", city="sakarya", center_lat=39.5, center_lon=30.0)

    assert contributor.contribute(north_region, context) > contributor.contribute(south_region, context)


def test_no_sectors_yields_neutral_multiplier():
    contributor = GrowthDirectionContributor()
    region = Region(id=1, name="r", city="sakarya", center_lat=40.5, center_lon=30.0)
    context = ScoringContext(points_of_interest=[CITY_CENTER], growth_direction_sectors=[])

    assert contributor.contribute(region, context) == 1.0


def test_no_city_center_poi_yields_neutral_multiplier():
    contributor = GrowthDirectionContributor()
    region = Region(id=1, name="r", city="sakarya", center_lat=40.5, center_lon=30.0)
    context = ScoringContext(points_of_interest=[], growth_direction_sectors=SECTORS)

    assert contributor.contribute(region, context) == 1.0
