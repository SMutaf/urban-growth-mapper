from dataclasses import dataclass
from typing import Optional


@dataclass
class LandCoverCell:
    """One pre-aggregated reading of local building density, on a coarse
    (~1km) grid across the whole city - not one row per OSM building (which
    would be hundreds of thousands of rows for a province and isn't needed,
    since the fringe signal only cares about local density, not individual
    building identity). Produced by scripts/ingest_sakarya_osm.py's
    building/farmland extraction - see FringeContributor for how this is
    used.
    """

    id: Optional[int]
    city: str
    latitude: float
    longitude: float
    building_count: int
    is_open_land: bool  # farmland/meadow/grass landuse present at this point
