import math
from typing import List, Tuple

EARTH_RADIUS_KM = 6371.0
KM_PER_LAT_DEGREE = 111.0


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def is_definitely_beyond(lat1: float, lon1: float, lat2: float, lon2: float, max_km: float) -> bool:
    """Cheap reject for "this point can't possibly be within max_km" using
    plain degree deltas instead of trig. Never returns True for a point that
    would actually be within max_km (a latitude-only degree delta is always
    <= the true great-circle distance), so callers can safely skip the
    expensive haversine call whenever this returns True.

    Exists to make summing a decay function over thousands of points
    (e.g. PoiProximityContributor at a fine grid resolution) affordable -
    most points are trivially far from a given region and don't need a full
    trig calculation to prove it.
    """
    lat_delta_km = abs(lat1 - lat2) * KM_PER_LAT_DEGREE
    if lat_delta_km > max_km:
        return True
    lon_delta_km = abs(lon1 - lon2) * KM_PER_LAT_DEGREE * math.cos(math.radians(lat1))
    return lon_delta_km > max_km


def point_in_polygon(lon: float, lat: float, ring: List[Tuple[float, float]]) -> bool:
    """Standard ray-casting point-in-polygon test. `ring` is a list of
    (lon, lat) vertices (doesn't need to be explicitly closed - first point
    repeated as the last is fine either way).

    Pure Python rather than a call into shapely (which infrastructure code
    uses freely) because the domain layer has no third-party dependencies -
    this is the one piece of polygon geometry a domain module (GridGenerator)
    needs to know about, to keep generated regions inside a real province
    boundary instead of a loose bounding rectangle.
    """
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat):
            x_intersect = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lon < x_intersect:
                inside = not inside
        j = i
    return inside
