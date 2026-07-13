"""Module 3: convergence analysis - the main output of this pipeline.

Answers: does refining the grid from resolution R to a finer resolution
actually change the result, or has the model already converged by R? A
fine grid's scores are spatially aggregated up into each coarse cell
(mean, or majority-vote for a hot/cold classification), then compared
against what the coarse grid computed directly for that same cell. Large
disagreement means refining mattered; small disagreement means it didn't.

Aggregation is done via a real spatial join (fine cell centroid -> which
coarse cell polygon contains it), not by assuming the two grids' cells
nest at round multiples - true for 1000/500/250 but NOT for 250/100
(250/100 = 2.5, not an integer), so a spatial join is the only approach
that's correct across this whole resolution ladder.
"""

from dataclasses import dataclass
from typing import Optional

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.stats import spearmanr


def aggregate_fine_to_coarse(
    fine_grid: gpd.GeoDataFrame,
    fine_scores: pd.DataFrame,
    coarse_grid: gpd.GeoDataFrame,
    hot_threshold: float,
) -> pd.DataFrame:
    """Returns one row per coarse cell_id with the fine grid's scores
    aggregated up into it: mean (for MAD/Spearman) and majority-vote
    "is_hot" share (for the Kappa-style classification agreement check).
    Coarse cells with no fine cell centroid inside them (can happen at a
    boundary sliver) are dropped from the comparison - they contribute no
    information either way.
    """
    fine_points = fine_grid[["cell_id", "geometry"]].copy()
    fine_points["geometry"] = fine_points.geometry.centroid
    fine_points = fine_points.merge(fine_scores, on="cell_id")

    joined = gpd.sjoin(
        fine_points, coarse_grid[["cell_id", "geometry"]], how="inner", predicate="within",
        lsuffix="fine", rsuffix="coarse",
    )
    if joined.empty:
        return pd.DataFrame(columns=["cell_id", "normalized_score", "hot_share"])

    joined["is_hot"] = joined["normalized_score"] >= hot_threshold
    agg = joined.groupby("cell_id_coarse").agg(
        normalized_score=("normalized_score", "mean"),
        hot_share=("is_hot", "mean"),
    )
    agg.index.name = "cell_id"
    return agg.reset_index()


def cohen_kappa(a: np.ndarray, b: np.ndarray) -> float:
    """Manual implementation (2-class case) rather than pulling in
    scikit-learn for one formula: kappa = (agreement - chance_agreement) /
    (1 - chance_agreement).
    """
    n = len(a)
    if n == 0:
        return float("nan")
    observed_agreement = np.mean(a == b)
    p_a1 = np.mean(a)
    p_b1 = np.mean(b)
    chance_agreement = p_a1 * p_b1 + (1 - p_a1) * (1 - p_b1)
    if chance_agreement >= 1.0:
        return 1.0 if observed_agreement >= 1.0 else 0.0
    return (observed_agreement - chance_agreement) / (1 - chance_agreement)


@dataclass
class ConvergenceMetrics:
    coarse_resolution_m: float
    fine_resolution_m: float
    n_compared_cells: int
    mad: float
    spearman_rho: float
    spearman_p: float
    kappa: float


def compute_convergence_metrics(
    coarse_resolution_m: float,
    fine_resolution_m: float,
    coarse_scores: pd.DataFrame,
    fine_aggregated: pd.DataFrame,
    hot_threshold: float,
) -> ConvergenceMetrics:
    merged = coarse_scores.reset_index().merge(fine_aggregated, on="cell_id", suffixes=("_coarse", "_fine"))
    if len(merged) < 2:
        return ConvergenceMetrics(coarse_resolution_m, fine_resolution_m, len(merged), float("nan"), float("nan"), float("nan"), float("nan"))

    mad = float(np.mean(np.abs(merged["normalized_score_coarse"] - merged["normalized_score_fine"])))
    rho, p_value = spearmanr(merged["normalized_score_coarse"], merged["normalized_score_fine"])

    coarse_is_hot = (merged["normalized_score_coarse"] >= hot_threshold).values
    fine_is_hot = (merged["hot_share"] >= 0.5).values
    kappa = cohen_kappa(coarse_is_hot, fine_is_hot)

    return ConvergenceMetrics(coarse_resolution_m, fine_resolution_m, len(merged), mad, float(rho), float(p_value), kappa)


def find_convergence_resolution(
    metrics_coarse_to_fine: list, mad_threshold: float
) -> Optional[float]:
    """`metrics_coarse_to_fine` is a list of ConvergenceMetrics ordered
    from the coarsest comparison to the finest (e.g. 1000-vs-500,
    500-vs-250, 250-vs-100). Returns the coarsest resolution R such that
    refining past R no longer meaningfully changes the score (its MAD
    against the next-finer grid is already under the threshold) - i.e. the
    recommended resolution. Returns None if even the finest tested
    resolution hasn't converged (refining further might still matter, and
    that should be reported honestly rather than guessed at).
    """
    for metric in metrics_coarse_to_fine:
        if metric.mad < mad_threshold:
            return metric.coarse_resolution_m
    return None
