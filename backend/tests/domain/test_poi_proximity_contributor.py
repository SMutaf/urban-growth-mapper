from app.domain.entities.point_of_interest import POICategory, PointOfInterest
from app.domain.entities.project import ProjectStatus
from app.domain.entities.region import Region
from app.domain.scoring.contributors.poi_proximity import PoiProximityContributor
from app.domain.scoring.scoring_context import ScoringContext


def test_region_closer_to_poi_scores_higher():
    contributor = PoiProximityContributor()
    hospital = PointOfInterest(
        id=1,
        name="Test Hastanesi",
        category=POICategory.HOSPITAL,
        status=ProjectStatus.COMPLETED,
        city="sakarya",
        latitude=40.77,
        longitude=30.40,
    )
    near_region = Region(id=1, name="near", city="sakarya", center_lat=40.771, center_lon=30.401)
    far_region = Region(id=2, name="far", city="sakarya", center_lat=41.50, center_lon=31.50)
    context = ScoringContext(points_of_interest=[hospital])

    assert contributor.contribute(near_region, context) > contributor.contribute(far_region, context)


def test_no_pois_yields_neutral_multiplier():
    contributor = PoiProximityContributor()
    region = Region(id=1, name="r", city="sakarya", center_lat=40.0, center_lon=30.0)

    assert contributor.contribute(region, ScoringContext(points_of_interest=[])) == 1.0


def test_metro_station_weighted_higher_than_bus_stop():
    contributor = PoiProximityContributor()
    region = Region(id=1, name="r", city="sakarya", center_lat=40.0, center_lon=30.0)
    metro = PointOfInterest(
        id=1, name="metro", category=POICategory.METRO_STATION, status=ProjectStatus.COMPLETED,
        city="sakarya", latitude=40.001, longitude=30.001,
    )
    bus_stop = PointOfInterest(
        id=2, name="bus", category=POICategory.BUS_STOP, status=ProjectStatus.COMPLETED,
        city="sakarya", latitude=40.001, longitude=30.001,
    )

    metro_contribution = contributor.contribute(region, ScoringContext(points_of_interest=[metro]))
    bus_contribution = contributor.contribute(region, ScoringContext(points_of_interest=[bus_stop]))

    assert metro_contribution > bus_contribution
