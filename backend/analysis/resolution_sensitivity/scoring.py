"""Module 2: wires this analysis to the REAL production scoring engine.

This project already has a real, fully-built equivalent of the task's
hypothetical `compute_growth_score(cell)`:
`app.domain.scoring.composite_scorer.CompositeHeatmapScorer.score_regions()`,
fed by a `ScoringContext` assembled from real ingested data (OSM
infrastructure, Sakarya municipal population stats, transit stops,
hospitals, schools - see the project's data-sourcing report for exact
origins). We reuse it directly rather than writing a placeholder, so every
result in this analysis reflects the actual live scoring model, not a
stand-in.

Cost split, and why: projects/POIs/hazard zones/growth-direction sectors
are city-wide facts that don't depend on where the grid's cell centers
land, so they're fetched from the DB exactly ONCE regardless of how many
resolutions or offsets are being tested (see SharedCityData). Only the
per-mahalle population growth-rate/momentum lookup genuinely depends on
each grid's specific cell centers (it's a point-in-polygon match), so
that's the one piece recomputed per grid - still a single batched query,
not one query per cell.
"""

import time
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.application.services.heatmap_service import HeatmapService
from app.core.di import build_heatmap_service
from app.domain.entities.hazard_zone import HazardZone
from app.domain.entities.land_use_profile import LandUseProfile
from app.domain.entities.point_of_interest import PointOfInterest
from app.domain.entities.project import Project
from app.domain.entities.region import Region
from app.domain.scoring.composite_scorer import CompositeHeatmapScorer
from app.domain.scoring.scoring_context import ScoringContext
from analysis.resolution_sensitivity.config import CITY


@dataclass
class SharedCityData:
    """Everything about Sakarya that's the same no matter what grid
    resolution/offset is being tested - fetched once per analysis run.
    """

    projects: List[Project]
    points_of_interest: List[PointOfInterest]
    hazard_zones: List[HazardZone]
    growth_direction_sectors: List[float]
    service: HeatmapService  # kept around to reuse its private per-region helper


def build_shared_city_data(session: Session, profile: LandUseProfile = LandUseProfile.BALANCED) -> SharedCityData:
    service = build_heatmap_service(session, profile)
    projects = service._project_repo.list_by_city(CITY)
    pois = service._poi_repo.list_by_city(CITY)
    hazards = service._hazard_repo.list_by_city(CITY)
    # Growth-direction sectors are computed from mahalle centroids city-wide
    # (see HeatmapService._compute_growth_direction_sectors) - genuinely
    # independent of which regions we're about to score, so this is safe
    # to compute once here rather than per resolution.
    sectors = service._compute_growth_direction_sectors(CITY, pois)
    return SharedCityData(projects, pois, hazards, sectors, service)


def regions_from_grid(cell_ids: np.ndarray, lons: np.ndarray, lats: np.ndarray) -> List[Region]:
    return [
        Region(id=int(cell_id), name=f"cell-{cell_id}", city=CITY, center_lat=float(lat), center_lon=float(lon))
        for cell_id, lon, lat in zip(cell_ids, lons, lats)
    ]


def build_context_for_regions(regions: List[Region], shared: SharedCityData) -> ScoringContext:
    # Reuses HeatmapService's own private helper for the region-dependent
    # growth-rate/momentum lookup rather than reimplementing it, so this
    # analysis can never silently drift from what the production endpoint
    # actually computes for the same regions.
    growth_rates, growth_momentum = shared.service._lookup_district_stats(CITY, regions)
    return ScoringContext(
        projects=shared.projects,
        points_of_interest=shared.points_of_interest,
        hazard_zones=shared.hazard_zones,
        region_growth_rates=growth_rates,
        region_growth_momentum=growth_momentum,
        growth_direction_sectors=shared.growth_direction_sectors,
    )


def score_grid(
    grid_cell_ids: np.ndarray,
    grid_lons: np.ndarray,
    grid_lats: np.ndarray,
    shared: SharedCityData,
    scorer: CompositeHeatmapScorer,
) -> pd.DataFrame:
    """Scores an arbitrary set of grid cell centers with the real
    production scoring pipeline. Returns a DataFrame indexed by cell_id
    with raw_score and normalized_score columns - normalized_score is a
    log-space min-max normalization *within this specific set of cells*
    (see domain/scoring/normalization.py), which is the same rule the live
    /heatmap endpoint follows. This matters for interpreting cross-
    resolution comparisons: a finer grid samples more of the province
    (including more low-scoring rural edge cells), which can shift the
    normalization range slightly independent of any real change in the
    underlying pattern - see report.py's caveats section.
    """
    regions = regions_from_grid(grid_cell_ids, grid_lons, grid_lats)
    context = build_context_for_regions(regions, shared)
    scores = scorer.score_regions(regions, context)
    return pd.DataFrame(
        {
            "cell_id": [s.region_id for s in scores],
            "raw_score": [s.raw_score for s in scores],
            "normalized_score": [s.normalized_score for s in scores],
        }
    ).set_index("cell_id")


def calibrate_scoring_cost(
    grid_lons: np.ndarray, grid_lats: np.ndarray, shared: SharedCityData, scorer: CompositeHeatmapScorer,
    sample_size: int = 500,
) -> float:
    """Measures real seconds-per-cell on a random subsample, so the
    pipeline can print an honest time estimate before committing to a full
    580k-cell (100m) run instead of guessing.
    """
    rng = np.random.default_rng(0)
    n = min(sample_size, len(grid_lons))
    idx = rng.choice(len(grid_lons), size=n, replace=False)
    start = time.perf_counter()
    score_grid(idx, grid_lons[idx], grid_lats[idx], shared, scorer)
    elapsed = time.perf_counter() - start
    return elapsed / n


def estimate_full_run_seconds(cell_count: int, seconds_per_cell: float) -> float:
    return cell_count * seconds_per_cell
