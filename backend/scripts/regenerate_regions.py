"""Replaces the stored heatmap grid for a city with a freshly generated one
at a new cell size.

The grid (Region rows) feeds both the heatmap endpoint and the frontend's
heatmap layer. Regions aren't scored/cached at generation time (scoring
happens live per /heatmap request), so this script only touches geometry.

Clipped to the city's real boundary polygon (app/core/city_bounds.py's
load_city_boundary), not just its bounding box - for an irregularly shaped
area like a whole province, the bbox alone covers ~2x the real land area
(Sakarya: ~10,300km2 bbox vs ~5,800km2 actual), which would score and color
map area that's actually in a neighbouring province or the sea.

Default resolution (1.0km) is a deliberate trade-off: covering the full
province at the previous 0.4km (tuned for just the Adapazari urban core)
would mean ~10x more regions than the old grid and push a live /heatmap
request well past 30s. 1.0km keeps the region count (and so response time)
in the same ballpark as before while covering the whole province - the
raster rendering (frontend/src/heatmapRaster.js) stays just as smooth at
any resolution since it bilinear-interpolates between grid points rather
than drawing them as discrete blobs.

Run with, from the backend/ directory:

    python scripts/regenerate_regions.py sakarya 1.0
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.city_bounds import CITY_BOUNDING_BOXES, load_city_boundary  # noqa: E402
from app.domain.grid.grid_generator import GridGenerator  # noqa: E402
from app.infrastructure.persistence.database import SessionLocal  # noqa: E402
from app.infrastructure.persistence.models import RegionModel  # noqa: E402
from app.infrastructure.persistence.repositories.region_repository import (  # noqa: E402
    SqlAlchemyRegionRepository,
)


def regenerate(city: str, cell_size_km: float) -> None:
    bbox = CITY_BOUNDING_BOXES[city]
    boundary = load_city_boundary(city)
    session = SessionLocal()
    try:
        deleted = session.query(RegionModel).filter(RegionModel.city == city).delete()
        session.commit()
        print(f"Deleted {deleted} existing regions for '{city}'.")

        regions = GridGenerator().generate(bbox, cell_size_km, boundary=boundary)
        SqlAlchemyRegionRepository(session).bulk_create(city, regions)
        clip_note = "clipped to real boundary" if boundary else "bbox only, no boundary file found"
        print(f"Created {len(regions)} regions at {cell_size_km}km resolution ({clip_note}).")
    finally:
        session.close()


if __name__ == "__main__":
    city_arg = sys.argv[1] if len(sys.argv) > 1 else "sakarya"
    cell_size_arg = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    regenerate(city_arg, cell_size_arg)
