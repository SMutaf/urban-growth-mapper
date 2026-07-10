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


def test_peak_band_beats_right_at_ramp():
    contributor = HighwayJunctionAccessContributor()
    context = ScoringContext(points_of_interest=[JUNCTION])

    right_at_ramp = contributor.contribute(_region_at_km_offset(0.0), context)
    peak_band = contributor.contribute(_region_at_km_offset(0.35), context)

    assert peak_band > right_at_ramp


def test_right_at_ramp_is_mildly_negative():
    contributor = HighwayJunctionAccessContributor()
    context = ScoringContext(points_of_interest=[JUNCTION])

    assert contributor.contribute(_region_at_km_offset(0.0), context) < 0


def test_far_away_has_no_effect():
    contributor = HighwayJunctionAccessContributor()
    context = ScoringContext(points_of_interest=[JUNCTION])

    assert contributor.contribute(_region_at_km_offset(2.0), context) == 0.0
