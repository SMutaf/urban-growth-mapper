from app.domain.entities.point_of_interest import POICategory, PointOfInterest
from app.domain.entities.project import ProjectStatus
from app.domain.entities.region import Region
from app.domain.scoring.contributors.rail_station_access import RailStationAccessContributor
from app.domain.scoring.scoring_context import ScoringContext

STATION = PointOfInterest(
    id=1, name="station", category=POICategory.TRAIN_STATION, status=ProjectStatus.COMPLETED,
    city="sakarya", latitude=40.0, longitude=30.0,
)


def _region_at_km_offset(km: float) -> Region:
    # ~111km per degree of latitude - close enough for a unit test.
    return Region(id=1, name="r", city="sakarya", center_lat=40.0 + km / 111.0, center_lon=30.0)


def test_inverted_u_shape_peak_beats_right_next_to_station():
    contributor = RailStationAccessContributor()
    context = ScoringContext(points_of_interest=[STATION])

    right_at_station = contributor.contribute(_region_at_km_offset(0.0), context)
    peak_band = contributor.contribute(_region_at_km_offset(0.6), context)

    assert peak_band > right_at_station


def test_inverted_u_shape_peak_beats_far_away():
    contributor = RailStationAccessContributor()
    context = ScoringContext(points_of_interest=[STATION])

    peak_band = contributor.contribute(_region_at_km_offset(0.6), context)
    far_away = contributor.contribute(_region_at_km_offset(5.0), context)

    assert peak_band > far_away


def test_right_at_station_is_penalised():
    contributor = RailStationAccessContributor()
    context = ScoringContext(points_of_interest=[STATION])

    assert contributor.contribute(_region_at_km_offset(0.0), context) < 1.0


def test_far_away_has_no_effect():
    contributor = RailStationAccessContributor()
    context = ScoringContext(points_of_interest=[STATION])

    assert contributor.contribute(_region_at_km_offset(5.0), context) == 1.0


def test_no_stations_yields_neutral_multiplier():
    contributor = RailStationAccessContributor()
    region = Region(id=1, name="r", city="sakarya", center_lat=40.0, center_lon=30.0)

    assert contributor.contribute(region, ScoringContext(points_of_interest=[])) == 1.0
