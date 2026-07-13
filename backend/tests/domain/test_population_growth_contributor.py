from app.domain.entities.region import Region
from app.domain.scoring.contributors.population_growth import PopulationGrowthContributor
from app.domain.scoring.scoring_context import ScoringContext


def test_growing_district_contributes_positively():
    contributor = PopulationGrowthContributor()
    region = Region(id=1, name="r", city="sakarya", center_lat=40.0, center_lon=30.0)
    context = ScoringContext(region_growth_rates={1: 0.02})

    assert contributor.contribute(region, context) > 1.0


def test_shrinking_district_contributes_negatively():
    contributor = PopulationGrowthContributor()
    region = Region(id=1, name="r", city="sakarya", center_lat=40.0, center_lon=30.0)
    context = ScoringContext(region_growth_rates={1: -0.01})

    assert contributor.contribute(region, context) < 1.0


def test_missing_growth_rate_yields_neutral_multiplier():
    contributor = PopulationGrowthContributor()
    region = Region(id=1, name="r", city="sakarya", center_lat=40.0, center_lon=30.0)

    assert contributor.contribute(region, ScoringContext(region_growth_rates={})) == 1.0


def test_higher_growth_rate_contributes_more():
    contributor = PopulationGrowthContributor()
    region = Region(id=1, name="r", city="sakarya", center_lat=40.0, center_lon=30.0)

    low = contributor.contribute(region, ScoringContext(region_growth_rates={1: 0.005}))
    high = contributor.contribute(region, ScoringContext(region_growth_rates={1: 0.02}))

    assert high > low
