"""Proves FringeContributor is a true opt-in addition: with its weight
forced to 0 (CompositeHeatmapScorer raises each contributor's multiplier
to its weight as a power - x**0 == 1, see composite_scorer.py), the score
for any region/context must come out BIT-FOR-BIT identical to what the
pre-fringe 13-contributor pipeline computed, regardless of what
land_cover_cells/fringe_density_band the context carries. This is what
"backward compatible, feature-flaggable" concretely means here - not just
an assertion that fringe *can* be disabled, but proof that disabling it
perfectly reproduces the old behavior.
"""

from app.domain.entities.hazard_zone import HazardZone, HazardType
from app.domain.entities.land_cover import LandCoverCell
from app.domain.entities.point_of_interest import POICategory, PointOfInterest
from app.domain.entities.project import Project, ProjectStatus, ProjectType
from app.domain.entities.region import Region
from app.domain.scoring.composite_scorer import CompositeHeatmapScorer
from app.domain.scoring.contributors.city_center_access import CityCenterAccessContributor
from app.domain.scoring.contributors.fringe import FringeContributor
from app.domain.scoring.contributors.growth_direction import GrowthDirectionContributor
from app.domain.scoring.contributors.hazard_penalty import HazardPenaltyContributor
from app.domain.scoring.contributors.highway_junction_access import HighwayJunctionAccessContributor
from app.domain.scoring.contributors.highway_noise import HighwayNoiseContributor
from app.domain.scoring.contributors.industrial_zone_access import IndustrialZoneAccessContributor
from app.domain.scoring.contributors.negative_externality import NegativeExternalityContributor
from app.domain.scoring.contributors.poi_proximity import PoiProximityContributor
from app.domain.scoring.contributors.population_growth import PopulationGrowthContributor
from app.domain.scoring.contributors.population_momentum import PopulationMomentumContributor
from app.domain.scoring.contributors.project_proximity import ProjectProximityContributor
from app.domain.scoring.contributors.rail_station_access import RailStationAccessContributor
from app.domain.scoring.contributors.railway_noise import RailwayNoiseContributor
from app.domain.scoring.contributors.university_proximity import UniversityProximityContributor
from app.domain.scoring.fringe_density_band import compute_density_band
from app.domain.scoring.scoring_context import ScoringContext

# Snapshot of di.py's contributor list exactly as it was before
# FringeContributor was added - the pre-fringe regression baseline this
# test compares against.
_PRE_FRINGE_CONTRIBUTORS = [
    ProjectProximityContributor(),
    PoiProximityContributor(),
    CityCenterAccessContributor(),
    HazardPenaltyContributor(),
    PopulationGrowthContributor(),
    PopulationMomentumContributor(),
    GrowthDirectionContributor(),
    RailwayNoiseContributor(),
    RailStationAccessContributor(),
    HighwayNoiseContributor(),
    HighwayJunctionAccessContributor(),
    UniversityProximityContributor(),
    IndustrialZoneAccessContributor(),
    NegativeExternalityContributor(),
]


def _realistic_context() -> ScoringContext:
    """A context with real signal on most factors (not an all-empty
    context, which would trivially score 1.0 x 1.0 x ... regardless of
    whether fringe is wired in or not and wouldn't actually exercise
    anything) - including land cover data, so this test proves fringe's
    weight=0 neutralizes it even when it WOULD otherwise have an effect.
    """
    city_center = PointOfInterest(
        id=1, name="center", category=POICategory.CITY_CENTER, status=ProjectStatus.COMPLETED,
        city="sakarya", latitude=40.75, longitude=30.39,
    )
    university = PointOfInterest(
        id=2, name="uni", category=POICategory.UNIVERSITY, status=ProjectStatus.COMPLETED,
        city="sakarya", latitude=40.74, longitude=30.35,
    )
    hospital = PointOfInterest(
        id=3, name="hospital", category=POICategory.HOSPITAL, status=ProjectStatus.COMPLETED,
        city="sakarya", latitude=40.755, longitude=30.40,
    )
    port = Project(
        id=1, name="port", project_type=ProjectType.PORT, status=ProjectStatus.COMPLETED,
        city="sakarya", latitude=41.10, longitude=30.60,
    )
    hazard = HazardZone(
        id=1, name="fault", hazard_type=HazardType.EARTHQUAKE, risk_level=0.6,
        city="sakarya", latitude=40.76, longitude=30.38,
    )
    land_cover_cells = [
        LandCoverCell(id=1, city="sakarya", latitude=40.75, longitude=30.39, building_count=40, is_open_land=False),
        LandCoverCell(id=2, city="sakarya", latitude=40.80, longitude=30.45, building_count=2, is_open_land=True),
    ]
    density_band = compute_density_band([c.building_count for c in land_cover_cells], 0.85, 1.20)

    return ScoringContext(
        projects=[port],
        points_of_interest=[city_center, university, hospital],
        hazard_zones=[hazard],
        region_growth_rates={1: 0.02, 2: -0.01},
        region_growth_momentum={1: 0.01, 2: -0.005},
        growth_direction_sectors=[0.01, 0.0, -0.01, 0.0, 0.02, 0.0, -0.02, 0.0],
        land_cover_cells=land_cover_cells,
        fringe_density_band=density_band,
    )


def test_fringe_weight_zero_reproduces_pre_fringe_scores_exactly():
    context = _realistic_context()
    regions = [
        Region(id=1, name="r1", city="sakarya", center_lat=40.751, center_lon=30.391),
        Region(id=2, name="r2", city="sakarya", center_lat=40.80, center_lon=30.45),
        Region(id=3, name="r3", city="sakarya", center_lat=41.05, center_lon=30.55),
    ]

    pre_fringe_scorer = CompositeHeatmapScorer(_PRE_FRINGE_CONTRIBUTORS)
    fringe_disabled_scorer = CompositeHeatmapScorer(
        [*_PRE_FRINGE_CONTRIBUTORS, FringeContributor()],
        weights=[1.0] * len(_PRE_FRINGE_CONTRIBUTORS) + [0.0],
    )

    pre_fringe_scores = pre_fringe_scorer.score_regions(regions, context)
    fringe_disabled_scores = fringe_disabled_scorer.score_regions(regions, context)

    for before, after in zip(pre_fringe_scores, fringe_disabled_scores):
        assert before.region_id == after.region_id
        assert before.raw_score == after.raw_score
        assert before.normalized_score == after.normalized_score


def test_fringe_weight_nonzero_actually_changes_at_least_one_score():
    # Sanity check that the test above isn't vacuously true because fringe
    # never influences anything in this context - with weight=1 it must
    # differ from the pre-fringe baseline for at least one region.
    context = _realistic_context()
    regions = [
        Region(id=1, name="r1", city="sakarya", center_lat=40.751, center_lon=30.391),
        Region(id=2, name="r2", city="sakarya", center_lat=40.80, center_lon=30.45),
    ]

    pre_fringe_scorer = CompositeHeatmapScorer(_PRE_FRINGE_CONTRIBUTORS)
    fringe_enabled_scorer = CompositeHeatmapScorer([*_PRE_FRINGE_CONTRIBUTORS, FringeContributor()])

    pre_fringe_scores = pre_fringe_scorer.score_regions(regions, context)
    fringe_enabled_scores = fringe_enabled_scorer.score_regions(regions, context)

    assert any(
        before.raw_score != after.raw_score
        for before, after in zip(pre_fringe_scores, fringe_enabled_scores)
    )
