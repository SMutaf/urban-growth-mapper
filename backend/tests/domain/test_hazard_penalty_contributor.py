from app.domain.entities.hazard_zone import HazardType, HazardZone
from app.domain.entities.region import Region
from app.domain.scoring.contributors.hazard_penalty import HazardPenaltyContributor
from app.domain.scoring.scoring_context import ScoringContext


def test_hazard_proximity_is_negative():
    contributor = HazardPenaltyContributor()
    earthquake_zone = HazardZone(
        id=1, name="fault line", hazard_type=HazardType.EARTHQUAKE, risk_level=0.8,
        city="sakarya", latitude=40.77, longitude=30.40,
    )
    region = Region(id=1, name="near", city="sakarya", center_lat=40.771, center_lon=30.401)

    contribution = contributor.contribute(region, ScoringContext(hazard_zones=[earthquake_zone]))

    assert contribution < 1.0


def test_closer_region_penalized_more_than_farther_region():
    contributor = HazardPenaltyContributor()
    earthquake_zone = HazardZone(
        id=1, name="fault line", hazard_type=HazardType.EARTHQUAKE, risk_level=0.8,
        city="sakarya", latitude=40.77, longitude=30.40,
    )
    near_region = Region(id=1, name="near", city="sakarya", center_lat=40.771, center_lon=30.401)
    far_region = Region(id=2, name="far", city="sakarya", center_lat=41.50, center_lon=31.50)
    context = ScoringContext(hazard_zones=[earthquake_zone])

    assert contributor.contribute(near_region, context) < contributor.contribute(far_region, context)


def test_no_hazard_zones_yields_neutral_multiplier():
    contributor = HazardPenaltyContributor()
    region = Region(id=1, name="r", city="sakarya", center_lat=40.0, center_lon=30.0)

    assert contributor.contribute(region, ScoringContext(hazard_zones=[])) == 1.0


def test_higher_risk_level_penalizes_more():
    contributor = HazardPenaltyContributor()
    region = Region(id=1, name="r", city="sakarya", center_lat=40.0, center_lon=30.0)
    low_risk = HazardZone(
        id=1, name="low", hazard_type=HazardType.EARTHQUAKE, risk_level=0.2,
        city="sakarya", latitude=40.001, longitude=30.001,
    )
    high_risk = HazardZone(
        id=2, name="high", hazard_type=HazardType.EARTHQUAKE, risk_level=0.9,
        city="sakarya", latitude=40.001, longitude=30.001,
    )

    low_contribution = contributor.contribute(region, ScoringContext(hazard_zones=[low_risk]))
    high_contribution = contributor.contribute(region, ScoringContext(hazard_zones=[high_risk]))

    assert high_contribution < low_contribution
