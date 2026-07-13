from app.domain.entities.land_cover import LandCoverCell
from app.domain.entities.point_of_interest import POICategory, PointOfInterest
from app.domain.entities.project import Project, ProjectStatus, ProjectType
from app.domain.entities.region import Region
from app.domain.scoring.contributors.fringe import (
    DENSITY_MAX_MULTIPLIER,
    DENSITY_MIN_MULTIPLIER,
    FringeContributor,
)
from app.domain.scoring.fringe_density_band import compute_density_band
from app.domain.scoring.scoring_context import ScoringContext


def _region_at_km_offset(km: float) -> Region:
    return Region(id=1, name="r", city="sakarya", center_lat=40.0 + km / 111.0, center_lon=30.0)


def _density_band():
    # 0 = empty rural, 50 = fringe sweet spot, 100 = saturated core.
    return compute_density_band(list(range(0, 101, 5)), DENSITY_MIN_MULTIPLIER, DENSITY_MAX_MULTIPLIER)


def test_no_land_cover_data_yields_neutral_multiplier():
    contributor = FringeContributor()
    region = Region(id=1, name="r", city="sakarya", center_lat=40.0, center_lon=30.0)
    context = ScoringContext()

    assert contributor.contribute(region, context) == 1.0


def test_moderate_density_near_built_edge_scores_higher_than_saturated_core():
    contributor = FringeContributor()
    band = _density_band()

    moderate_density_cell = LandCoverCell(
        id=1, city="sakarya", latitude=40.0, longitude=30.0, building_count=50, is_open_land=False
    )
    saturated_cell = LandCoverCell(
        id=2, city="sakarya", latitude=40.0, longitude=30.0, building_count=100, is_open_land=False
    )
    built_edge = LandCoverCell(
        id=3, city="sakarya", latitude=40.0 + 0.5 / 111.0, longitude=30.0, building_count=10, is_open_land=False
    )

    fringe_context = ScoringContext(
        land_cover_cells=[moderate_density_cell, built_edge], fringe_density_band=band
    )
    saturated_context = ScoringContext(
        land_cover_cells=[saturated_cell, built_edge], fringe_density_band=band
    )

    region = Region(id=1, name="r", city="sakarya", center_lat=40.0, center_lon=30.0)
    fringe_score = contributor.contribute(region, fringe_context)
    saturated_score = contributor.contribute(region, saturated_context)

    assert fringe_score > saturated_score


def test_far_from_any_built_up_area_is_penalised():
    contributor = FringeContributor()
    band = _density_band()
    moderate_density_cell = LandCoverCell(
        id=1, city="sakarya", latitude=40.0, longitude=30.0, building_count=50, is_open_land=True
    )
    context = ScoringContext(land_cover_cells=[moderate_density_cell], fringe_density_band=band)

    near_region = Region(id=1, name="near", city="sakarya", center_lat=40.0, center_lon=30.0)
    far_region = _region_at_km_offset(20.0)

    near_score = contributor.contribute(near_region, context)
    far_score = contributor.contribute(far_region, context)

    assert near_score > far_score


def test_leapfrog_exception_neutralises_edge_penalty_near_university():
    contributor = FringeContributor()
    band = _density_band()

    # A remote, moderate-density cell with NO built-up neighbour nearby -
    # would normally be penalised by the edge-distance component.
    remote_cell = LandCoverCell(
        id=1, city="sakarya", latitude=41.0, longitude=31.0, building_count=50, is_open_land=True
    )
    university = PointOfInterest(
        id=1, name="uni", category=POICategory.UNIVERSITY, status=ProjectStatus.COMPLETED,
        city="sakarya", latitude=41.0, longitude=31.0,
    )
    region = Region(id=1, name="remote", city="sakarya", center_lat=41.0, center_lon=31.0)

    with_university = ScoringContext(
        land_cover_cells=[remote_cell], fringe_density_band=band, points_of_interest=[university]
    )
    without_university = ScoringContext(land_cover_cells=[remote_cell], fringe_density_band=band)

    score_with = contributor.contribute(region, with_university)
    score_without = contributor.contribute(region, without_university)

    assert score_with > score_without


def test_leapfrog_exception_does_not_double_count_positive_bonus():
    # Refined leapfrog rule: near an attractor, the edge component is
    # NEUTRALISED (1.0), not turned positive - the attractor's own pull is
    # already counted by its own contributor elsewhere in the pipeline.
    contributor = FringeContributor()
    band = _density_band()
    remote_cell = LandCoverCell(
        id=1, city="sakarya", latitude=41.0, longitude=31.0, building_count=50, is_open_land=True
    )
    university = PointOfInterest(
        id=1, name="uni", category=POICategory.UNIVERSITY, status=ProjectStatus.COMPLETED,
        city="sakarya", latitude=41.0, longitude=31.0,
    )
    region = Region(id=1, name="remote", city="sakarya", center_lat=41.0, center_lon=31.0)
    context = ScoringContext(land_cover_cells=[remote_cell], fringe_density_band=band, points_of_interest=[university])

    score = contributor.contribute(region, context)
    density_only = contributor._density_multiplier(region, context)

    assert score == density_only  # edge component contributed exactly 1.0, not a bonus


def test_leapfrog_buffer_reuses_osb_contributor_own_band_width():
    contributor = FringeContributor()
    band = _density_band()
    remote_cell = LandCoverCell(
        id=1, city="sakarya", latitude=41.0, longitude=31.0, building_count=50, is_open_land=True
    )
    osb = Project(
        id=1, name="osb", project_type=ProjectType.INDUSTRIAL_ZONE, status=ProjectStatus.COMPLETED,
        city="sakarya", latitude=41.0, longitude=31.0,
    )
    region = Region(id=1, name="remote", city="sakarya", center_lat=41.0, center_lon=31.0)
    context = ScoringContext(land_cover_cells=[remote_cell], fringe_density_band=band, projects=[osb])

    score_with_osb = contributor.contribute(region, context)
    score_without_osb = contributor.contribute(region, ScoringContext(land_cover_cells=[remote_cell], fringe_density_band=band))

    assert score_with_osb > score_without_osb
