from app.domain.entities.hazard_zone import HazardType, HazardZone
from app.domain.entities.point_of_interest import POICategory, PointOfInterest
from app.domain.entities.project import Project, ProjectStatus, ProjectType
from app.domain.entities.region import Region
from app.domain.scoring.composite_scorer import CompositeHeatmapScorer
from app.domain.scoring.contributors.hazard_penalty import HazardPenaltyContributor
from app.domain.scoring.contributors.poi_proximity import PoiProximityContributor
from app.domain.scoring.contributors.project_proximity import ProjectProximityContributor
from app.domain.scoring.scoring_context import ScoringContext


def _scorer():
    return CompositeHeatmapScorer(
        [ProjectProximityContributor(), PoiProximityContributor(), HazardPenaltyContributor()]
    )


def test_region_near_project_and_poi_scores_higher_than_empty_region():
    scorer = _scorer()
    project = Project(
        id=1, name="Liman", project_type=ProjectType.PORT, status=ProjectStatus.COMPLETED,
        city="sakarya", latitude=40.77, longitude=30.40,
    )
    hospital = PointOfInterest(
        id=1, name="Hastane", category=POICategory.HOSPITAL, status=ProjectStatus.COMPLETED,
        city="sakarya", latitude=40.77, longitude=30.40,
    )
    near_region = Region(id=1, name="near", city="sakarya", center_lat=40.771, center_lon=30.401)
    far_region = Region(id=2, name="far", city="sakarya", center_lat=41.50, center_lon=31.50)
    context = ScoringContext(projects=[project], points_of_interest=[hospital])

    scores = {s.region_id: s.normalized_score for s in scorer.score_regions([near_region, far_region], context)}

    assert scores[1] > scores[2]


def test_hazard_zone_lowers_score_relative_to_no_hazard():
    project = Project(
        id=1, name="Liman", project_type=ProjectType.PORT, status=ProjectStatus.COMPLETED,
        city="sakarya", latitude=40.0, longitude=30.0,
    )
    region = Region(id=1, name="r", city="sakarya", center_lat=40.001, center_lon=30.001)
    other_region = Region(id=2, name="other", city="sakarya", center_lat=45.0, center_lon=35.0)
    earthquake_zone = HazardZone(
        id=1, name="fault", hazard_type=HazardType.EARTHQUAKE, risk_level=0.8,
        city="sakarya", latitude=40.001, longitude=30.001,
    )

    without_hazard = _scorer().score_regions(
        [region, other_region], ScoringContext(projects=[project])
    )
    with_hazard = _scorer().score_regions(
        [region, other_region], ScoringContext(projects=[project], hazard_zones=[earthquake_zone])
    )

    raw_without = next(s.raw_score for s in without_hazard if s.region_id == 1)
    raw_with = next(s.raw_score for s in with_hazard if s.region_id == 1)

    assert raw_with < raw_without


def test_empty_context_yields_zero_scores():
    scorer = _scorer()
    region = Region(id=1, name="r", city="sakarya", center_lat=40.0, center_lon=30.0)

    scores = scorer.score_regions([region], ScoringContext())

    assert scores[0].raw_score == 0.0
