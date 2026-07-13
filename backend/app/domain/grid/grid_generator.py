import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

from app.domain.entities.region import Region
from app.domain.geo_utils import point_in_polygon

KM_PER_LAT_DEGREE = 111.0
KM_PER_LON_DEGREE_AT_EQUATOR = 111.320


@dataclass
class BoundingBox:
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float


class GridGenerator:
    """Splits a bounding box into square grid cells used as MVP 'regions'.

    A placeholder for real neighbourhood (mahalle) boundaries, which can later
    replace this generator behind the same IRegionRepository without touching
    the scoring logic.
    """

    def generate(
        self,
        bbox: BoundingBox,
        cell_size_km: float,
        boundary: Optional[List[Tuple[float, float]]] = None,
    ) -> List[Region]:
        """`boundary`, if given, is a (lon, lat) ring - cells whose center
        falls outside it are skipped. Without it, `bbox` alone is used,
        which is fine for a roughly rectangular area but wastes a lot of
        scored area (and can bleed into a neighbouring province/the sea) for
        an irregularly shaped one like a whole province - see
        scripts/regenerate_regions.py for where the real Sakarya boundary
        comes from.
        """
        mid_lat = (bbox.min_lat + bbox.max_lat) / 2
        lat_step = cell_size_km / KM_PER_LAT_DEGREE
        lon_step = cell_size_km / (KM_PER_LON_DEGREE_AT_EQUATOR * math.cos(math.radians(mid_lat)))

        regions: List[Region] = []
        index = 0
        lat = bbox.min_lat
        while lat < bbox.max_lat:
            lon = bbox.min_lon
            while lon < bbox.max_lon:
                center_lat = lat + lat_step / 2
                center_lon = lon + lon_step / 2
                # A partial edge cell can have its center fall just outside the
                # bbox - skip it rather than reporting a region outside the
                # city bounds the caller asked for.
                if center_lat <= bbox.max_lat and center_lon <= bbox.max_lon:
                    if boundary is None or point_in_polygon(center_lon, center_lat, boundary):
                        regions.append(
                            Region(
                                id=index,
                                name=f"cell-{index}",
                                city="",
                                center_lat=center_lat,
                                center_lon=center_lon,
                            )
                        )
                        index += 1
                lon += lon_step
            lat += lat_step
        return regions
