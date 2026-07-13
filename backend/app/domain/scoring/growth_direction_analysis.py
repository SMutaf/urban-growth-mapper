import math
from typing import List, Tuple

NUM_SECTORS = 8


def bearing_degrees(from_lat: float, from_lon: float, to_lat: float, to_lon: float) -> float:
    """Compass bearing in degrees [0, 360) from one point to another - 0 is
    north, 90 is east, clockwise.
    """
    phi1 = math.radians(from_lat)
    phi2 = math.radians(to_lat)
    d_lambda = math.radians(to_lon - from_lon)
    x = math.sin(d_lambda) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(d_lambda)
    return math.degrees(math.atan2(x, y)) % 360


def compute_sector_growth(
    points: List[Tuple[float, float, float]],
    center_lat: float,
    center_lon: float,
    num_sectors: int = NUM_SECTORS,
) -> List[float]:
    """Weighted-average growth rate per compass sector (index 0 = the sector
    centered on north, clockwise), expressed *relative to the city's overall
    average* - a value of +0.01 means "this direction grows 1 percentage
    point faster than Sakarya as a whole", not an absolute rate. That's the
    point: a region's raw proximity/amenity score already captures "is this
    a good spot", this captures "is this the direction the city is actually
    expanding towards" on top of that.

    `points` is (lat, lon, growth_rate) per mahalle centroid - deliberately
    not per-region, since this needs the full city-wide picture regardless
    of which regions the current heatmap grid happens to cover.
    """
    if not points:
        return [0.0] * num_sectors

    overall_avg = sum(rate for _, _, rate in points) / len(points)
    sector_width = 360.0 / num_sectors

    sector_totals = [0.0] * num_sectors
    sector_counts = [0] * num_sectors
    for lat, lon, rate in points:
        bearing = bearing_degrees(center_lat, center_lon, lat, lon)
        sector = round(bearing / sector_width) % num_sectors
        sector_totals[sector] += rate
        sector_counts[sector] += 1

    return [
        (sector_totals[i] / sector_counts[i] - overall_avg) if sector_counts[i] > 0 else 0.0
        for i in range(num_sectors)
    ]


def sector_value_at_bearing(sectors: List[float], bearing: float) -> float:
    """Smoothly interpolates between the two nearest sector centers rather
    than hard-binning, so a region right at a sector boundary doesn't see an
    arbitrary jump in score. Sector i's center is at bearing i * (360 /
    len(sectors)), matching how compute_sector_growth assigns points.
    """
    if not sectors:
        return 0.0
    num_sectors = len(sectors)
    sector_width = 360.0 / num_sectors
    position = (bearing % 360) / sector_width
    lower = int(math.floor(position)) % num_sectors
    upper = (lower + 1) % num_sectors
    t = position - math.floor(position)
    return sectors[lower] + t * (sectors[upper] - sectors[lower])
