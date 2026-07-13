"""Module 1: multi-resolution regular square grid generation.

Grids are built in a pure-Python/GeoPandas path (numpy + shapely boxes)
rather than via PostGIS ST_SquareGrid, even though the latter is available
(PostGIS 3.4 on this project's DB). Reasons: (a) grid geometry generation
is CPU-bound, not data-bound - there's no need to round-trip cell
geometries through the database, especially at the 100m rung where that
would mean serializing/deserializing several hundred thousand polygons;
(b) offset sweeps (see maup_offset.py) need many grid variants generated
back-to-back, which is far cheaper as in-memory numpy arithmetic than as
repeated SQL calls. The real database is still used for its actual job:
supplying the scoring inputs (projects, POIs, hazard zones, population
data) - see scoring.py.
"""

import json
import time
from dataclasses import dataclass
from typing import List

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Polygon, box
from shapely.prepared import prep

from analysis.resolution_sensitivity import config


def load_city_boundary_gdf() -> gpd.GeoDataFrame:
    """Loads the same real Sakarya province boundary the production
    heatmap grid is clipped to (see app/core/city_bounds.py) - one
    GeoDataFrame, WGS84, single polygon row.
    """
    with open(config.CITY_BOUNDARY_GEOJSON, encoding="utf-8") as f:
        geojson = json.load(f)
    polygon = Polygon(geojson["coordinates"][0])
    return gpd.GeoDataFrame({"city": [config.CITY]}, geometry=[polygon], crs=config.CRS_GEOGRAPHIC)


def generate_square_grid(
    boundary_metric: gpd.GeoSeries,
    cell_size_m: float,
    offset_x_m: float = 0.0,
    offset_y_m: float = 0.0,
) -> gpd.GeoDataFrame:
    """Square grid clipped to `boundary_metric` (already in a metric CRS),
    keeping a cell only if its CENTER falls inside the boundary - this
    mirrors the exact semantics of the production grid
    (domain/grid/grid_generator.py's point_in_polygon check on the cell
    center), so results here stay comparable to what the live app actually
    computes rather than a differently-clipped approximation.

    `offset_x_m`/`offset_y_m` shift the grid origin - used by
    maup_offset.py to test whether results are an artifact of where the
    grid happens to start.
    """
    minx, miny, maxx, maxy = boundary_metric.total_bounds
    minx += offset_x_m
    miny += offset_y_m

    xs = np.arange(minx, maxx + cell_size_m, cell_size_m)
    ys = np.arange(miny, maxy + cell_size_m, cell_size_m)

    boundary_union = boundary_metric.union_all()

    # Candidate cell origins and their centers, built once as flat arrays
    # (not a Python double-loop over shapely calls) - at the 100m rung this
    # is several hundred thousand candidates, and only a spatial-index
    # backed vectorized filter (below) keeps that affordable.
    grid_x0, grid_y0 = np.meshgrid(xs, ys, indexing="ij")
    grid_x0 = grid_x0.ravel()
    grid_y0 = grid_y0.ravel()
    centers_x = grid_x0 + cell_size_m / 2
    centers_y = grid_y0 + cell_size_m / 2

    # A plain GeoSeries.within(single_polygon) call re-derives GEOS's
    # internal spatial index of `boundary_union` on every element instead
    # of once - fine for a few thousand points, but at the 100m rung
    # (500k+ candidates) against this province boundary's ~3000-vertex
    # ring it's minutes of wasted work. shapely.prepared.prep() builds
    # that index once and reuses it for every point-in-polygon test -
    # this is the standard fix for "many points, one fixed complex
    # polygon" and changes nothing about which cells are kept, only how
    # fast the same test runs.
    prepared_boundary = prep(boundary_union)
    centers = gpd.GeoSeries(gpd.points_from_xy(centers_x, centers_y), crs=boundary_metric.crs)
    inside_mask = np.array([prepared_boundary.contains(pt) for pt in centers.values])

    kept_cells = [
        box(x0, y0, x0 + cell_size_m, y0 + cell_size_m)
        for x0, y0, keep in zip(grid_x0, grid_y0, inside_mask)
        if keep
    ]
    kept_centers = centers[inside_mask].reset_index(drop=True)

    grid = gpd.GeoDataFrame(
        {
            "cell_id": range(len(kept_cells)),
            "center_x_m": kept_centers.x.values,
            "center_y_m": kept_centers.y.values,
        },
        geometry=kept_cells,
        crs=boundary_metric.crs,
    )

    centers_wgs84 = kept_centers.to_crs(config.CRS_GEOGRAPHIC)
    grid["center_lon"] = centers_wgs84.x.values
    grid["center_lat"] = centers_wgs84.y.values
    return grid


@dataclass
class GridStats:
    resolution_m: float
    cell_count: int
    generation_seconds: float


def log_grid_stats_for_resolutions(
    boundary_metric: gpd.GeoSeries, resolutions_m: List[float]
) -> pd.DataFrame:
    """Generates each resolution's grid once (offset 0,0) purely to report
    cell counts and generation timing - the per-resolution scoring cost
    estimate (the more expensive step) is calibrated separately in
    scoring.py, since geometry generation and scoring have very different
    per-cell costs.
    """
    rows = []
    for resolution_m in resolutions_m:
        start = time.perf_counter()
        grid = generate_square_grid(boundary_metric, resolution_m)
        elapsed = time.perf_counter() - start
        rows.append(GridStats(resolution_m, len(grid), elapsed))
        print(
            f"  {resolution_m:>5.0f} m -> {len(grid):>7,} cells "
            f"(geometry generation: {elapsed:.2f}s)"
        )
    return pd.DataFrame([r.__dict__ for r in rows])
