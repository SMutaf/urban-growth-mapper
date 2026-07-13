"""Module 5: adaptive (quadtree-style) grid.

Instead of refining the whole province uniformly, only split cells that
look like an active growth front - everywhere else stays coarse. A cell is
split into 4 children (halved in both x and y) if:
  (a) HOT: its score is at/above a high percentile of the starting coarse
      grid's own distribution, or
  (b) HETEROGENEOUS: it disagrees sharply with its immediate grid
      neighbours (a literal "edge of expansion" - a sudden score gradient
      between adjacent cells), or
  (c) NEAR KEY INFRASTRUCTURE: within a buffer distance of a university,
      OSB, highway junction, or the CBD - independent locations the
      literature associates with growth fronts, on top of whatever the
      model's own score says.
Splitting continues down to ADAPTIVE_FINE_FLOOR_M. Homogeneous, un-hot,
infrastructure-poor cells are left at their original (coarser) size.

Design notes on two subtleties this module has to get right:

1. Split decisions use RAW score, not normalized_score, and the
   hot-threshold is a quantile of the STARTING coarse grid's raw scores.
   normalize_scores() log-min-maxes over whatever batch of cells it's
   given (see domain/scoring/normalization.py) - scoring children level by
   level in separate batches would otherwise produce normalized_score
   values that aren't comparable across levels or to each other. Only
   after every leaf cell (at whatever depth it stopped at) has been
   collected do we run ONE final normalization pass over the complete
   adaptive set - see build_adaptive_grid()'s last step.

2. Heterogeneity (criterion b) is only evaluated at the top (coarse)
   level, using the coarse grid's regular row/column structure for exact
   neighbour lookups. Re-deriving "immediate neighbours" at every deeper
   recursion level would need maintaining full sibling adjacency at each
   depth for comparatively little extra benefit here - hot-score and
   infrastructure-buffer criteria (both single-cell, location-only checks)
   still drive further refinement at deeper levels.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple

import geopandas as gpd
import numpy as np
import pandas as pd

from app.domain.entities.point_of_interest import POICategory
from app.domain.entities.project import ProjectType
from analysis.resolution_sensitivity import config, grid_generation, scoring

_EARTH_RADIUS_KM = 6371.0


def _haversine_km_vectorized(lat1: np.ndarray, lon1: np.ndarray, lat2: float, lon2: float) -> np.ndarray:
    """numpy-array-friendly haversine - the domain layer's
    haversine_distance_km (app/domain/geo_utils.py) is deliberately plain
    Python/math (no numpy dependency, per the domain layer's no-third-
    party-deps rule), which only accepts scalars. This analysis module
    isn't part of the domain layer, so it's free to vectorize; same
    formula, same constant.
    """
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    d_phi = np.radians(lat2 - lat1)
    d_lambda = np.radians(lon2 - lon1)
    a = np.sin(d_phi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(d_lambda / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


@dataclass
class AdaptiveLeaf:
    center_x: float
    center_y: float
    size_m: float
    depth: int


def _infra_points_lonlat(shared: scoring.SharedCityData) -> np.ndarray:
    """(lon, lat) of every university, highway junction, OSB, and the CBD
    reference point - the independent "growth front" infra signal (see
    criterion c above). No planned/under-construction infrastructure or
    TOKİ/zoning-conversion data is used here because this project doesn't
    have that data (see the project's data-sourcing report, section 5.1) -
    only what's actually ingested from OSM/municipal sources.
    """
    points = []
    for poi in shared.points_of_interest:
        if poi.category in (POICategory.UNIVERSITY, POICategory.HIGHWAY_JUNCTION, POICategory.CITY_CENTER):
            points.append((poi.longitude, poi.latitude))
    for project in shared.projects:
        if project.project_type == ProjectType.INDUSTRIAL_ZONE:
            points.append((project.longitude, project.latitude))
    return np.array(points)


def _near_infra_mask(lons: np.ndarray, lats: np.ndarray, infra_lonlat: np.ndarray, buffer_km: float) -> np.ndarray:
    if len(infra_lonlat) == 0:
        return np.zeros(len(lons), dtype=bool)
    # Vectorized haversine: every candidate cell against every infra point
    # (a few dozen) - cheap even for tens of thousands of candidates.
    min_dist_km = np.full(len(lons), np.inf)
    for infra_lon, infra_lat in infra_lonlat:
        dist = _haversine_km_vectorized(lats, lons, infra_lat, infra_lon)
        min_dist_km = np.minimum(min_dist_km, dist)
    return min_dist_km <= buffer_km


def _score_candidates_raw(
    centers_x: np.ndarray, centers_y: np.ndarray, boundary_metric: gpd.GeoSeries,
    shared: scoring.SharedCityData, scorer,
) -> np.ndarray:
    if len(centers_x) == 0:
        return np.array([])
    centers_wgs84 = gpd.GeoSeries(
        gpd.points_from_xy(centers_x, centers_y), crs=boundary_metric.crs
    ).to_crs(config.CRS_GEOGRAPHIC)
    cell_ids = np.arange(len(centers_x))
    scored = scoring.score_grid(cell_ids, centers_wgs84.x.values, centers_wgs84.y.values, shared, scorer)
    return scored["raw_score"].reindex(cell_ids).values


def _coarse_grid_with_indices(boundary_metric: gpd.GeoSeries, cell_size_m: float) -> gpd.GeoDataFrame:
    grid = grid_generation.generate_square_grid(boundary_metric, cell_size_m)
    minx, miny, _, _ = boundary_metric.total_bounds
    grid["ix"] = np.floor((grid["center_x_m"] - minx) / cell_size_m).astype(int)
    grid["iy"] = np.floor((grid["center_y_m"] - miny) / cell_size_m).astype(int)
    return grid


def build_adaptive_grid(
    boundary_metric: gpd.GeoSeries,
    shared: scoring.SharedCityData,
    scorer,
) -> Tuple[pd.DataFrame, dict]:
    """Returns (leaves_df, stats) - leaves_df has one row per final
    adaptive cell (center_lon, center_lat, size_m, depth, raw_score,
    normalized_score); stats reports how much smaller this is than a
    uniform fine-resolution grid over the same area, for the report.
    """
    infra_lonlat = _infra_points_lonlat(shared)

    coarse = _coarse_grid_with_indices(boundary_metric, config.ADAPTIVE_COARSE_M)
    coarse_raw = _score_candidates_raw(
        coarse["center_x_m"].values, coarse["center_y_m"].values, boundary_metric, shared, scorer
    )
    coarse["raw_score"] = coarse_raw

    hot_threshold = float(np.quantile(coarse_raw, config.ADAPTIVE_HOT_SCORE_PERCENTILE))

    score_by_index: Dict[Tuple[int, int], float] = {
        (row.ix, row.iy): row.raw_score for row in coarse.itertuples()
    }

    def neighbour_mean(ix: int, iy: int) -> float:
        neighbours = [
            score_by_index.get((ix - 1, iy)), score_by_index.get((ix + 1, iy)),
            score_by_index.get((ix, iy - 1)), score_by_index.get((ix, iy + 1)),
        ]
        present = [v for v in neighbours if v is not None]
        return float(np.mean(present)) if present else np.nan

    coarse["neighbour_mean"] = [neighbour_mean(row.ix, row.iy) for row in coarse.itertuples()]
    coarse["is_hot"] = coarse["raw_score"] >= hot_threshold
    coarse["is_heterogeneous"] = (
        (coarse["neighbour_mean"] > 0)
        & ((coarse["raw_score"] - coarse["neighbour_mean"]).abs() / coarse["neighbour_mean"] > config.ADAPTIVE_HETEROGENEITY_THRESHOLD)
    )
    coarse["is_near_infra"] = _near_infra_mask(
        coarse["center_lon"].values, coarse["center_lat"].values, infra_lonlat, config.ADAPTIVE_INFRA_BUFFER_M / 1000
    )
    coarse["should_split"] = coarse["is_hot"] | coarse["is_heterogeneous"] | coarse["is_near_infra"]

    leaves: List[AdaptiveLeaf] = []
    uniform_fine_equivalent_count = 0

    current_level_x = coarse.loc[coarse["should_split"], "center_x_m"].values
    current_level_y = coarse.loc[coarse["should_split"], "center_y_m"].values
    current_size = config.ADAPTIVE_COARSE_M

    for _, row in coarse.loc[~coarse["should_split"]].iterrows():
        leaves.append(AdaptiveLeaf(row["center_x_m"], row["center_y_m"], config.ADAPTIVE_COARSE_M, depth=0))
        cells_per_side = config.ADAPTIVE_COARSE_M / config.ADAPTIVE_FINE_FLOOR_M
        uniform_fine_equivalent_count += cells_per_side * cells_per_side

    depth = 1
    while current_size > config.ADAPTIVE_FINE_FLOOR_M and len(current_level_x) > 0:
        child_size = current_size / 2
        offsets = [(-child_size / 2, -child_size / 2), (child_size / 2, -child_size / 2),
                   (-child_size / 2, child_size / 2), (child_size / 2, child_size / 2)]
        child_x = np.concatenate([current_level_x + dx for dx, dy in offsets])
        child_y = np.concatenate([current_level_y + dy for dx, dy in offsets])

        child_raw = _score_candidates_raw(child_x, child_y, boundary_metric, shared, scorer)
        centers_lonlat = gpd.GeoSeries(gpd.points_from_xy(child_x, child_y), crs=boundary_metric.crs).to_crs(config.CRS_GEOGRAPHIC)
        child_near_infra = _near_infra_mask(centers_lonlat.x.values, centers_lonlat.y.values, infra_lonlat, config.ADAPTIVE_INFRA_BUFFER_M / 1000)

        is_hot = child_raw >= hot_threshold
        should_split = is_hot | child_near_infra

        will_recurse = child_size > config.ADAPTIVE_FINE_FLOOR_M
        for x, y, raw, split in zip(child_x, child_y, child_raw, should_split):
            if will_recurse and split:
                continue  # goes into next level's current_level_x/y below
            leaves.append(AdaptiveLeaf(x, y, child_size, depth))
            cells_per_side = child_size / config.ADAPTIVE_FINE_FLOOR_M
            uniform_fine_equivalent_count += max(cells_per_side * cells_per_side, 1)

        if will_recurse:
            keep = should_split
            current_level_x = child_x[keep]
            current_level_y = child_y[keep]
        else:
            current_level_x = np.array([])
            current_level_y = np.array([])
        current_size = child_size
        depth += 1

    leaves_x = np.array([leaf.center_x for leaf in leaves])
    leaves_y = np.array([leaf.center_y for leaf in leaves])
    leaves_centers_lonlat = gpd.GeoSeries(gpd.points_from_xy(leaves_x, leaves_y), crs=boundary_metric.crs).to_crs(config.CRS_GEOGRAPHIC)

    shared_ids = np.arange(len(leaves))
    final_scores = scoring.score_grid(shared_ids, leaves_centers_lonlat.x.values, leaves_centers_lonlat.y.values, shared, scorer)

    leaves_df = pd.DataFrame({
        "cell_id": shared_ids,
        "center_lon": leaves_centers_lonlat.x.values,
        "center_lat": leaves_centers_lonlat.y.values,
        "size_m": [leaf.size_m for leaf in leaves],
        "depth": [leaf.depth for leaf in leaves],
    }).merge(final_scores.reset_index(), on="cell_id")

    uniform_fine_total = uniform_fine_equivalent_count
    stats = {
        "n_leaves": len(leaves_df),
        "n_coarse_cells_at_start": len(coarse),
        "n_split_at_top_level": int(coarse["should_split"].sum()),
        "uniform_fine_grid_equivalent_cells": int(uniform_fine_total),
        "savings_factor": (uniform_fine_total / len(leaves_df)) if len(leaves_df) else float("nan"),
    }
    return leaves_df, stats
