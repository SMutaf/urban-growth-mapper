from app.domain.entities.region import Region
from app.domain.scoring.contributors.population_momentum import PopulationMomentumContributor
from app.domain.scoring.scoring_context import ScoringContext


def test_accelerating_district_contributes_positively():
    contributor = PopulationMomentumContributor()
    region = Region(id=1, name="r", city="sakarya", center_lat=40.0, center_lon=30.0)
    context = ScoringContext(region_growth_momentum={1: 0.015})

    assert contributor.contribute(region, context) > 1.0


def test_decelerating_district_contributes_negatively():
    contributor = PopulationMomentumContributor()
    region = Region(id=1, name="r", city="sakarya", center_lat=40.0, center_lon=30.0)
    context = ScoringContext(region_growth_momentum={1: -0.01})

    assert contributor.contribute(region, context) < 1.0


def test_missing_momentum_yields_neutral_multiplier():
    contributor = PopulationMomentumContributor()
    region = Region(id=1, name="r", city="sakarya", center_lat=40.0, center_lon=30.0)

    assert contributor.contribute(region, ScoringContext(region_growth_momentum={})) == 1.0


def test_stronger_acceleration_contributes_more():
    contributor = PopulationMomentumContributor()
    region = Region(id=1, name="r", city="sakarya", center_lat=40.0, center_lon=30.0)

    mild = contributor.contribute(region, ScoringContext(region_growth_momentum={1: 0.005}))
    strong = contributor.contribute(region, ScoringContext(region_growth_momentum={1: 0.02}))

    assert strong > mild
