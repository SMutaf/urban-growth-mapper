from app.domain.entities.project import Project, ProjectStatus, ProjectType
from app.domain.entities.region import Region
from app.domain.scoring.contributors.industrial_zone_access import IndustrialZoneAccessContributor
from app.domain.scoring.scoring_context import ScoringContext

ZONE = Project(
    id=1, name="osb", project_type=ProjectType.INDUSTRIAL_ZONE, status=ProjectStatus.COMPLETED,
    city="sakarya", latitude=40.0, longitude=30.0,
)


def _region_at_km_offset(km: float) -> Region:
    return Region(id=1, name="r", city="sakarya", center_lat=40.0 + km / 111.0, center_lon=30.0)


def test_right_adjacent_is_negative():
    contributor = IndustrialZoneAccessContributor()
    context = ScoringContext(projects=[ZONE])

    assert contributor.contribute(_region_at_km_offset(0.0), context) < 0


def test_commutershed_peak_beats_right_adjacent():
    contributor = IndustrialZoneAccessContributor()
    context = ScoringContext(projects=[ZONE])

    right_adjacent = contributor.contribute(_region_at_km_offset(0.0), context)
    commutershed_peak = contributor.contribute(_region_at_km_offset(2.0), context)

    assert commutershed_peak > right_adjacent


def test_commutershed_peak_beats_far_away():
    contributor = IndustrialZoneAccessContributor()
    context = ScoringContext(projects=[ZONE])

    commutershed_peak = contributor.contribute(_region_at_km_offset(2.0), context)
    far_away = contributor.contribute(_region_at_km_offset(10.0), context)

    assert commutershed_peak > far_away


def test_no_zones_yields_zero():
    contributor = IndustrialZoneAccessContributor()
    region = Region(id=1, name="r", city="sakarya", center_lat=40.0, center_lon=30.0)

    assert contributor.contribute(region, ScoringContext(projects=[])) == 0.0
