from app.domain.entities.project import Project, ProjectStatus, ProjectType
from app.domain.entities.region import Region
from app.domain.scoring.contributors.project_proximity import ProjectProximityContributor
from app.domain.scoring.scoring_context import ScoringContext


def test_region_closer_to_project_scores_higher():
    contributor = ProjectProximityContributor()
    project = Project(
        id=1,
        name="Test YHT",
        project_type=ProjectType.RAILWAY,
        status=ProjectStatus.COMPLETED,
        city="sakarya",
        latitude=40.77,
        longitude=30.40,
        importance=1.0,
    )
    near_region = Region(id=1, name="near", city="sakarya", center_lat=40.771, center_lon=30.401)
    far_region = Region(id=2, name="far", city="sakarya", center_lat=41.50, center_lon=31.50)
    context = ScoringContext(projects=[project])

    assert contributor.contribute(near_region, context) > contributor.contribute(far_region, context)


def test_no_projects_yields_zero_contribution():
    contributor = ProjectProximityContributor()
    region = Region(id=1, name="r", city="sakarya", center_lat=40.0, center_lon=30.0)

    assert contributor.contribute(region, ScoringContext(projects=[])) == 0.0


def test_planned_project_contributes_less_than_completed():
    contributor = ProjectProximityContributor()
    region = Region(id=1, name="r", city="sakarya", center_lat=40.0, center_lon=30.0)
    planned = Project(
        id=1, name="planned", project_type=ProjectType.HIGHWAY, status=ProjectStatus.PLANNED,
        city="sakarya", latitude=40.001, longitude=30.001,
    )
    completed = Project(
        id=2, name="completed", project_type=ProjectType.HIGHWAY, status=ProjectStatus.COMPLETED,
        city="sakarya", latitude=40.001, longitude=30.001,
    )

    planned_contribution = contributor.contribute(region, ScoringContext(projects=[planned]))
    completed_contribution = contributor.contribute(region, ScoringContext(projects=[completed]))

    assert completed_contribution > planned_contribution
