from app.domain.entities.point_of_interest import POICategory, PointOfInterest
from app.domain.entities.project import ProjectStatus
from app.domain.entities.region import Region
from app.domain.scoring.contributors.negative_externality import NegativeExternalityContributor
from app.domain.scoring.scoring_context import ScoringContext

PRISON = PointOfInterest(
    id=1, name="prison", category=POICategory.PRISON, status=ProjectStatus.COMPLETED,
    city="sakarya", latitude=40.0, longitude=30.0,
)
LANDFILL = PointOfInterest(
    id=2, name="landfill", category=POICategory.LANDFILL, status=ProjectStatus.COMPLETED,
    city="sakarya", latitude=40.0, longitude=30.0,
)
CEMETERY = PointOfInterest(
    id=3, name="cemetery", category=POICategory.CEMETERY, status=ProjectStatus.COMPLETED,
    city="sakarya", latitude=40.0, longitude=30.0,
)


def _region_at_km_offset(km: float) -> Region:
    return Region(id=1, name="r", city="sakarya", center_lat=40.0 + km / 111.0, center_lon=30.0)


def test_close_to_prison_is_penalised():
    contributor = NegativeExternalityContributor()
    context = ScoringContext(points_of_interest=[PRISON])

    assert contributor.contribute(_region_at_km_offset(0.0), context) < 1.0


def test_far_from_prison_has_no_penalty():
    contributor = NegativeExternalityContributor()
    context = ScoringContext(points_of_interest=[PRISON])

    assert contributor.contribute(_region_at_km_offset(3.0), context) == 1.0


def test_no_lulus_yields_neutral_multiplier():
    contributor = NegativeExternalityContributor()
    region = Region(id=1, name="r", city="sakarya", center_lat=40.0, center_lon=30.0)

    assert contributor.contribute(region, ScoringContext(points_of_interest=[])) == 1.0


def test_multiple_lulus_stack():
    contributor = NegativeExternalityContributor()
    context_one = ScoringContext(points_of_interest=[PRISON])
    context_two = ScoringContext(points_of_interest=[PRISON, LANDFILL])

    penalty_one = contributor.contribute(_region_at_km_offset(0.0), context_one)
    penalty_two = contributor.contribute(_region_at_km_offset(0.0), context_two)

    assert penalty_two < penalty_one


def test_cemetery_penalty_is_milder_than_prison():
    contributor = NegativeExternalityContributor()
    prison_penalty = contributor.contribute(
        _region_at_km_offset(0.0), ScoringContext(points_of_interest=[PRISON])
    )
    cemetery_penalty = contributor.contribute(
        _region_at_km_offset(0.0), ScoringContext(points_of_interest=[CEMETERY])
    )

    assert cemetery_penalty > prison_penalty
