from app.domain.entities.point_of_interest import POICategory, PointOfInterest
from app.domain.entities.project import ProjectStatus
from app.domain.entities.region import Region
from app.domain.scoring.contributors.university_proximity import UniversityProximityContributor
from app.domain.scoring.scoring_context import ScoringContext

UNIVERSITY = PointOfInterest(
    id=1, name="university", category=POICategory.UNIVERSITY, status=ProjectStatus.COMPLETED,
    city="sakarya", latitude=40.0, longitude=30.0,
)


def _region_at_km_offset(km: float) -> Region:
    return Region(id=1, name="r", city="sakarya", center_lat=40.0 + km / 111.0, center_lon=30.0)


def test_close_to_university_beats_far_away():
    contributor = UniversityProximityContributor()
    context = ScoringContext(points_of_interest=[UNIVERSITY])

    close = contributor.contribute(_region_at_km_offset(0.5), context)
    far = contributor.contribute(_region_at_km_offset(6.0), context)

    assert close > far


def test_right_at_university_is_positive():
    contributor = UniversityProximityContributor()
    context = ScoringContext(points_of_interest=[UNIVERSITY])

    assert contributor.contribute(_region_at_km_offset(0.0), context) > 0


def test_beyond_range_has_no_effect():
    contributor = UniversityProximityContributor()
    context = ScoringContext(points_of_interest=[UNIVERSITY])

    assert contributor.contribute(_region_at_km_offset(6.0), context) == 0.0


def test_no_universities_yields_zero():
    contributor = UniversityProximityContributor()
    region = Region(id=1, name="r", city="sakarya", center_lat=40.0, center_lon=30.0)

    assert contributor.contribute(region, ScoringContext(points_of_interest=[])) == 0.0
