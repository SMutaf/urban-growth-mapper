from app.domain.entities.project import Project, ProjectStatus, ProjectType
from app.domain.entities.region import Region
from app.domain.scoring.contributors.railway_noise import RailwayNoiseContributor
from app.domain.scoring.scoring_context import ScoringContext


def _railway(lat=40.0, lon=30.0):
    return Project(
        id=1, name="rail", project_type=ProjectType.RAILWAY, status=ProjectStatus.COMPLETED,
        city="sakarya", latitude=lat, longitude=lon,
    )


def test_right_next_to_line_is_penalised():
    contributor = RailwayNoiseContributor()
    region = Region(id=1, name="r", city="sakarya", center_lat=40.0, center_lon=30.0)

    assert contributor.contribute(region, ScoringContext(projects=[_railway()])) < 1.0


def test_far_from_line_has_no_penalty():
    contributor = RailwayNoiseContributor()
    region = Region(id=1, name="r", city="sakarya", center_lat=41.0, center_lon=31.0)

    assert contributor.contribute(region, ScoringContext(projects=[_railway()])) == 1.0


def test_no_railways_yields_neutral_multiplier():
    contributor = RailwayNoiseContributor()
    region = Region(id=1, name="r", city="sakarya", center_lat=40.0, center_lon=30.0)

    assert contributor.contribute(region, ScoringContext(projects=[])) == 1.0
