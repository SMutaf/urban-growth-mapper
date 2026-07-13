from app.domain.geo_utils import haversine_distance_km, is_definitely_beyond, point_in_polygon

SQUARE = [(0.0, 0.0), (0.0, 2.0), (2.0, 2.0), (2.0, 0.0)]


def test_is_definitely_beyond_true_for_far_point():
    assert is_definitely_beyond(40.0, 30.0, 41.0, 31.0, max_km=20.0) is True


def test_is_definitely_beyond_false_for_near_point():
    assert is_definitely_beyond(40.0, 30.0, 40.01, 30.01, max_km=20.0) is False


def test_never_rejects_a_point_actually_within_max_km():
    lat1, lon1, lat2, lon2 = 40.0, 30.0, 40.15, 30.2
    max_km = haversine_distance_km(lat1, lon1, lat2, lon2) + 0.01
    assert is_definitely_beyond(lat1, lon1, lat2, lon2, max_km) is False


def test_point_in_polygon_true_for_interior_point():
    assert point_in_polygon(1.0, 1.0, SQUARE) is True


def test_point_in_polygon_false_for_exterior_point():
    assert point_in_polygon(5.0, 5.0, SQUARE) is False


def test_point_in_polygon_false_just_outside_edge():
    assert point_in_polygon(2.5, 1.0, SQUARE) is False
