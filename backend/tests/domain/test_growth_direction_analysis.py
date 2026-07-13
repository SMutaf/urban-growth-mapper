from app.domain.scoring.growth_direction_analysis import (
    bearing_degrees,
    compute_sector_growth,
    sector_value_at_bearing,
)


def test_bearing_due_north_is_zero():
    assert bearing_degrees(40.0, 30.0, 41.0, 30.0) == 0


def test_bearing_due_east_is_ninety():
    bearing = bearing_degrees(40.0, 30.0, 40.0, 31.0)
    assert 89 < bearing < 91


def test_bearing_due_south_is_180():
    bearing = bearing_degrees(40.0, 30.0, 39.0, 30.0)
    assert 179 < bearing < 181


def test_sector_growth_highlights_the_faster_growing_direction():
    # North points grow fast (5%), south points grow slow (1%) - the north
    # sector should come out clearly above the south sector once centered
    # on the overall average.
    points = [
        (41.0, 30.0, 0.05),
        (41.0, 30.01, 0.05),
        (39.0, 30.0, 0.01),
        (39.0, 30.01, 0.01),
    ]
    sectors = compute_sector_growth(points, center_lat=40.0, center_lon=30.0)

    assert sectors[0] > sectors[4]  # index 0 = north, index 4 = south (8 sectors, 45 deg each)


def test_sector_growth_with_no_points_is_all_zero():
    assert compute_sector_growth([], center_lat=40.0, center_lon=30.0) == [0.0] * 8


def test_sector_value_at_bearing_matches_exact_sector_center():
    sectors = [1.0, 0.0, 0.0, 0.0, -1.0, 0.0, 0.0, 0.0]
    assert sector_value_at_bearing(sectors, 0) == 1.0
    assert sector_value_at_bearing(sectors, 180) == -1.0


def test_sector_value_at_bearing_interpolates_between_neighbours():
    sectors = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    halfway_to_next = sector_value_at_bearing(sectors, 22.5)  # halfway between sector 0 and 1
    assert 0.4 < halfway_to_next < 0.6
