from app.domain.entities.point_of_interest import POICategory, PointOfInterest
from app.domain.entities.project import ProjectStatus
from app.domain.entities.region import Region
from app.domain.scoring.contributors.highway_junction_access import (
    HighwayJunctionAccessContributor,
)
from app.domain.scoring.scoring_context import ScoringContext

JUNCTION = PointOfInterest(
    id=1, name="junction", category=POICategory.HIGHWAY_JUNCTION, status=ProjectStatus.COMPLETED,
    city="sakarya", latitude=40.0, longitude=30.0,
)


def _region_at_km_offset(km: float) -> Region:
    return Region(id=1, name="r", city="sakarya", center_lat=40.0 + km / 111.0, center_lon=30.0)


def test_golden_zone_beats_right_at_ramp():
    contributor = HighwayJunctionAccessContributor()
    context = ScoringContext(points_of_interest=[JUNCTION])

    right_at_ramp = contributor.contribute(_region_at_km_offset(0.0), context)
    golden_zone = contributor.contribute(_region_at_km_offset(3.0), context)

    assert golden_zone > right_at_ramp


def test_right_at_ramp_is_mildly_penalised():
    contributor = HighwayJunctionAccessContributor()
    context = ScoringContext(points_of_interest=[JUNCTION])

    assert contributor.contribute(_region_at_km_offset(0.0), context) < 1.0


def test_golden_zone_spans_one_to_five_km():
    # The literature's "interchange effect" golden zone is 1-5km, not the
    # few hundred metres a naive reading of "near the highway" might
    # suggest - a region 2km out should clearly benefit.
    contributor = HighwayJunctionAccessContributor()
    context = ScoringContext(points_of_interest=[JUNCTION])

    assert contributor.contribute(_region_at_km_offset(2.0), context) > 1.0


def test_far_beyond_golden_zone_is_neutral():
    contributor = HighwayJunctionAccessContributor()
    context = ScoringContext(points_of_interest=[JUNCTION])

    assert contributor.contribute(_region_at_km_offset(10.0), context) == 1.0
