"""Module 4: MAUP offset (grid alignment) stability check.

The Modifiable Areal Unit Problem: a regular grid's cell boundaries are an
arbitrary analyst choice, not a property of the underlying geography. If
shifting where the grid *starts* (with no change to cell size) meaningfully
changes a location's score, that resolution's results are partly an
artifact of the grid, not a stable read of the real spatial pattern.

Method: generate a fixed set of real-world probe points (random locations
inside the province, independent of any grid), then for each of several
grid-origin offsets at a given resolution, work out which cell each probe
falls in and score just that cell.

Two deliberate design choices, both load-bearing for correctness, not just
speed:

1. We score RAW score, not normalized_score. normalize_scores() (see
   domain/scoring/normalization.py) log-min-maxes across whatever set of
   cells it's given - every contributor otherwise depends only on that
   one cell's own location plus city-wide data (projects/POIs/hazards/
   growth stats), never on other cells in the batch. So raw_score for a
   given point is identical whether it's scored alone or as part of a
   580,000-cell grid, while normalized_score would shift depending on
   which other cells happened to be in the sample - comparing normalized
   scores across offsets would conflate "the grid moved" with "the
   sample driving the normalization range changed", which is exactly the
   kind of artifact this test exists to rule out.

2. We work out each probe's cell by direct arithmetic (floor division by
   cell size from the offset grid's origin), not by generating and
   spatially joining the full grid - at the 100m rung that's the
   difference between scoring ~3,000 cells and ~580,000 cells to answer
   the same question, since a probe's raw score only depends on that one
   cell's center coordinates.
"""

from dataclasses import dataclass
from typing import List

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.prepared import prep

from analysis.resolution_sensitivity import config, scoring


def generate_probe_points(boundary_metric: gpd.GeoSeries, n: int, seed: int) -> gpd.GeoDataFrame:
    """Fixed random locations inside the real province boundary, reused
    across every resolution/offset combination so comparisons are
    apples-to-apples and don't scale with a resolution's full cell count.
    """
    boundary_union = boundary_metric.union_all()
    minx, miny, maxx, maxy = boundary_metric.total_bounds
    rng = np.random.default_rng(seed)

    points = []
    # Rejection sampling: the province is a fairly irregular shape inside
    # its bounding box, so roughly 40-60% of uniform box samples land
    # outside it - just keep drawing until we have enough.
    while len(points) < n:
        batch = n - len(points)
        xs = rng.uniform(minx, maxx, size=batch * 3)
        ys = rng.uniform(miny, maxy, size=batch * 3)
        candidates = gpd.GeoSeries(gpd.points_from_xy(xs, ys), crs=boundary_metric.crs)
        inside = candidates[candidates.within(boundary_union)]
        points.extend(inside.tolist()[:batch])

    probes = gpd.GeoDataFrame({"probe_id": range(n)}, geometry=points[:n], crs=boundary_metric.crs)
    return probes


def _cell_centers_for_probes(
    probe_x: np.ndarray, probe_y: np.ndarray, boundary_metric: gpd.GeoSeries,
    cell_size_m: float, offset_x_m: float, offset_y_m: float,
) -> np.ndarray:
    """For each probe, the center (in metric CRS) of the cell it would
    fall into on a regular grid of the given cell size and origin offset -
    pure arithmetic, matching generate_square_grid's own cell placement
    (grid lines at boundary.minx + offset + k*cell_size). Returns NaN rows
    for probes whose derived cell center falls outside the real province
    boundary (i.e. that cell wouldn't exist in the actual clipped grid at
    this offset - see grid_generation.generate_square_grid).
    """
    minx, miny, _, _ = boundary_metric.total_bounds
    origin_x = minx + offset_x_m
    origin_y = miny + offset_y_m

    cell_ix = np.floor((probe_x - origin_x) / cell_size_m)
    cell_iy = np.floor((probe_y - origin_y) / cell_size_m)
    center_x = origin_x + (cell_ix + 0.5) * cell_size_m
    center_y = origin_y + (cell_iy + 0.5) * cell_size_m

    prepared_boundary = prep(boundary_metric.union_all())
    valid = np.array([
        prepared_boundary.contains(pt) for pt in gpd.points_from_xy(center_x, center_y)
    ])
    center_x = np.where(valid, center_x, np.nan)
    center_y = np.where(valid, center_y, np.nan)
    return center_x, center_y


@dataclass
class OffsetStabilityResult:
    resolution_m: float
    offsets_tested: int
    n_probes_with_full_coverage: int
    mean_std: float
    p90_std: float
    max_std: float
    is_stable: bool


def test_offset_stability(
    resolution_m: float,
    boundary_metric: gpd.GeoSeries,
    probes_metric: gpd.GeoDataFrame,
    shared: scoring.SharedCityData,
    scorer,
) -> OffsetStabilityResult:
    offset_m_values = [f * resolution_m for f in config.MAUP_OFFSET_FRACTIONS]
    probe_x = probes_metric.geometry.x.values
    probe_y = probes_metric.geometry.y.values
    n_probes = len(probes_metric)

    raw_scores_by_offset = []
    for offset_x in offset_m_values:
        for offset_y in offset_m_values:
            center_x, center_y = _cell_centers_for_probes(
                probe_x, probe_y, boundary_metric, resolution_m, offset_x, offset_y
            )
            valid_mask = ~np.isnan(center_x)
            centers_wgs84 = gpd.GeoSeries(
                gpd.points_from_xy(center_x[valid_mask], center_y[valid_mask]), crs=boundary_metric.crs
            ).to_crs(config.CRS_GEOGRAPHIC)

            cell_ids = np.where(valid_mask)[0]
            scored = scoring.score_grid(cell_ids, centers_wgs84.x.values, centers_wgs84.y.values, shared, scorer)

            raw = np.full(n_probes, np.nan)
            raw[cell_ids] = scored["raw_score"].reindex(cell_ids).values
            raw_scores_by_offset.append(raw)

    scores_matrix = pd.DataFrame(np.column_stack(raw_scores_by_offset))
    fully_covered = scores_matrix.dropna(how="any")
    # Coefficient of variation (std/mean), not raw std: raw_score's
    # absolute scale varies a lot cell to cell (roughly 0.4 to 11+ across
    # this model - see scoring.py's describe() output), so a fixed
    # absolute-std threshold would flag naturally-large-scored cells as
    # "unstable" even with tiny relative movement. raw_score is always
    # strictly positive (the multiplicative model's contributors never
    # emit exactly 0 or negative - see contributors/interfaces.py), so
    # dividing by the mean is always safe here.
    stds = fully_covered.std(axis=1, ddof=0) / fully_covered.mean(axis=1)

    mean_std = float(stds.mean()) if len(stds) else float("nan")
    p90_std = float(stds.quantile(0.9)) if len(stds) else float("nan")
    max_std = float(stds.max()) if len(stds) else float("nan")

    return OffsetStabilityResult(
        resolution_m=resolution_m,
        offsets_tested=len(offset_m_values) ** 2,
        n_probes_with_full_coverage=len(fully_covered),
        mean_std=mean_std,
        p90_std=p90_std,
        max_std=max_std,
        is_stable=(p90_std < config.MAUP_INSTABILITY_STD_THRESHOLD) if len(stds) else False,
    )


def run_offset_stability_for_resolutions(
    resolutions_m: List[float],
    boundary_metric: gpd.GeoSeries,
    shared: scoring.SharedCityData,
    scorer,
) -> List[OffsetStabilityResult]:
    probes = generate_probe_points(boundary_metric, config.PROBE_SAMPLE_SIZE, config.RANDOM_SEED)
    results = []
    for resolution_m in resolutions_m:
        result = test_offset_stability(resolution_m, boundary_metric, probes, shared, scorer)
        results.append(result)
        stability = "STABLE" if result.is_stable else "UNSTABLE (grid-dependent)"
        print(
            f"  {resolution_m:>5.0f} m -> {result.offsets_tested} offsets, "
            f"mean raw-score std={result.mean_std:.4f}, p90 std={result.p90_std:.4f} -> {stability}"
        )
    return results
