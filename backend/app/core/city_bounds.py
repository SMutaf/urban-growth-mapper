import json
from pathlib import Path
from typing import List, Optional, Tuple

from app.domain.grid.grid_generator import BoundingBox

# The real Sakarya province extent (from the OSM relation 223462 boundary -
# see data/sakarya_boundary.geojson), replacing the original MVP-era box
# that only covered the Adapazari/Serdivan/Erenler urban core. The
# bounding box alone is much bigger than the province itself (an irregular
# shape - see load_city_boundary), so region generation should always pass
# the boundary polygon too to avoid scoring/coloring area that's actually
# in Kocaeli or the Black Sea.
CITY_BOUNDING_BOXES = {
    "sakarya": BoundingBox(min_lat=40.2944, max_lat=41.351, min_lon=29.9670, max_lon=31.0127),
}

_DATA_DIR = Path(__file__).resolve().parent / "data"
CITY_BOUNDARY_FILES = {
    "sakarya": _DATA_DIR / "sakarya_boundary.geojson",
}


def load_city_boundary(city: str) -> Optional[List[Tuple[float, float]]]:
    """Returns the city's real boundary as a (lon, lat) ring, or None if no
    boundary file is configured for it - callers should fall back to the
    plain bounding box in that case.
    """
    path = CITY_BOUNDARY_FILES.get(city)
    if path is None or not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        geojson = json.load(f)
    # GeoJSON coordinates are already [lon, lat] - polygon's first ring is
    # the outer boundary (interior rings/holes aren't relevant at province
    # scale here).
    return [tuple(point) for point in geojson["coordinates"][0]]
