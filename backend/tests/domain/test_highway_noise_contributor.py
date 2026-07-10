from app.domain.entities.project import Project, ProjectStatus, ProjectType
from app.domain.entities.region import Region
from app.domain.scoring.contributors.highway_noise import HighwayNoiseContributor
from app.domain.scoring.scoring_context import ScoringContext


def _highway(lat=40.0, lon=30.0):
    return Project(
        id=1, name="road", project_type=ProjectType.HIGHWAY, status=ProjectStatus.COMPLETED,
        city="sakarya", latitude=lat, longitude=lon,
    )


def test_right_next_to_highway_is_negative():
    contributor = HighwayNoiseContributor()
    region = Region(id=1, name="r", city="sakarya", center_lat=40.0, center_lon=30.0)

    assert contributor.contribute(region, ScoringContext(projects=[_highway()])) < 0


def test_far_from_highway_has_no_penalty():
    contributor = HighwayNoiseContributor()
    region = Region(id=1, name="r", city="sakarya", center_lat=41.0, center_lon=31.0)

    assert contributor.contribute(region, ScoringContext(projects=[_highway()])) == 0.0
