from app.domain.entities.point_of_interest import POICategory, PointOfInterest
from app.domain.entities.project import ProjectStatus
from app.domain.entities.region import Region
from app.domain.scoring.contributors.city_center_access import CityCenterAccessContributor
from app.domain.scoring.scoring_context import ScoringContext

CENTER = PointOfInterest(
    id=1, name="center", category=POICategory.CITY_CENTER, status=ProjectStatus.COMPLETED,
    city="sakarya", latitude=40.0, longitude=30.0,
)


def _region_at_km_offset(km: float) -> Region:
    return Region(id=1, name="r", city="sakarya", center_lat=40.0 + km / 111.0, center_lon=30.0)


def test_closer_to_center_scores_higher():
    contributor = CityCenterAccessContributor()
    context = ScoringContext(points_of_interest=[CENTER])

    close = contributor.contribute(_region_at_km_offset(1.0), context)
    far = contributor.contribute(_region_at_km_offset(20.0), context)

    assert close > far


def test_right_at_center_is_boosted_not_penalised():
    contributor = CityCenterAccessContributor()
    context = ScoringContext(points_of_interest=[CENTER])

    assert contributor.contribute(_region_at_km_offset(0.0), context) > 1.0


def test_beyond_province_scale_is_a_penalty_not_neutral():
    contributor = CityCenterAccessContributor()
    context = ScoringContext(points_of_interest=[CENTER])

    assert contributor.contribute(_region_at_km_offset(30.0), context) < 1.0


def test_no_city_center_yields_neutral_multiplier():
    contributor = CityCenterAccessContributor()
    region = Region(id=1, name="r", city="sakarya", center_lat=40.0, center_lon=30.0)

    assert contributor.contribute(region, ScoringContext(points_of_interest=[])) == 1.0
