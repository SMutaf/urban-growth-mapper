"""Orchestrates modules 1-6 end to end. See
scripts/run_resolution_sensitivity_analysis.py for the CLI entry point.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.di import _build_scorer
from app.domain.entities.land_use_profile import LandUseProfile
from analysis.resolution_sensitivity import (
    adaptive_grid,
    config,
    convergence,
    grid_generation,
    input_resolution,
    maup_offset,
    report,
    scoring,
)


def run(
    session: Session,
    resolutions_m: List[float],
    profile: LandUseProfile = LandUseProfile.BALANCED,
    run_maup_offset_check: bool = True,
    run_adaptive_grid: bool = True,
    scoring_calibration_sample: int = 500,
) -> str:
    resolutions_sorted = sorted(resolutions_m, reverse=True)  # coarse -> fine, required by convergence logic

    print("Sınır ve ızgaralar yükleniyor...")
    boundary = grid_generation.load_city_boundary_gdf()
    boundary_metric = boundary.geometry.to_crs(config.CRS_METRIC)

    print("\n1) Çok-çözünürlüklü ızgara üretimi")
    grid_stats_df = grid_generation.log_grid_stats_for_resolutions(boundary_metric, resolutions_sorted)

    print("\nGerçek skorlama motoru bağlanıyor (proje/POI/tehlike/nüfus verisi tek seferlik çekiliyor)...")
    shared = scoring.build_shared_city_data(session, profile)
    scorer = _build_scorer(profile)

    print("\n2) Her çözünürlükte skor hesabı")
    grids = {}
    scores_by_resolution = {}
    for resolution_m in resolutions_sorted:
        grid = grid_generation.generate_square_grid(boundary_metric, resolution_m)
        seconds_per_cell = scoring.calibrate_scoring_cost(
            grid["center_lon"].values, grid["center_lat"].values, shared, scorer, scoring_calibration_sample
        )
        estimate_s = scoring.estimate_full_run_seconds(len(grid), seconds_per_cell)
        print(f"  {resolution_m:.0f} m: {len(grid):,} hücre, tahmini süre ~{estimate_s:.0f}s ({estimate_s/60:.1f} dk)...")

        scores = scoring.score_grid(grid["cell_id"].values, grid["center_lon"].values, grid["center_lat"].values, shared, scorer)
        grids[resolution_m] = grid
        scores_by_resolution[resolution_m] = scores
        print(f"    tamamlandı - ortalama skor {scores['normalized_score'].mean():.3f}, medyan {scores['normalized_score'].median():.3f}")

    print("\n3) Yakınsama analizi")
    coarsest_scores = scores_by_resolution[resolutions_sorted[0]]
    hot_threshold = coarsest_scores["normalized_score"].quantile(config.ADAPTIVE_HOT_SCORE_PERCENTILE)

    convergence_metrics = []
    for coarse_res, fine_res in zip(resolutions_sorted, resolutions_sorted[1:]):
        aggregated = convergence.aggregate_fine_to_coarse(
            grids[fine_res], scores_by_resolution[fine_res].reset_index(), grids[coarse_res], hot_threshold
        )
        metric = convergence.compute_convergence_metrics(
            coarse_res, fine_res, scores_by_resolution[coarse_res], aggregated, hot_threshold
        )
        convergence_metrics.append(metric)
        print(f"  {coarse_res:.0f}m ↔ {fine_res:.0f}m: MAD={metric.mad:.4f}, Spearman={metric.spearman_rho:.4f}, Kappa={metric.kappa:.4f}")

    convergence_resolution_m = convergence.find_convergence_resolution(convergence_metrics, config.CONVERGENCE_MAD_THRESHOLD)

    offset_results = []
    if run_maup_offset_check:
        print("\n4) MAUP ofset/hiza kontrolü")
        offset_results = maup_offset.run_offset_stability_for_resolutions(resolutions_sorted, boundary_metric, shared, scorer)

    adaptive_stats = {}
    if run_adaptive_grid:
        print("\n5) Uyarlanabilir (quadtree) ızgara")
        _, adaptive_stats = adaptive_grid.build_adaptive_grid(boundary_metric, shared, scorer)
        print(f"  {adaptive_stats['n_leaves']:,} nihai hücre (düzenli ince ızgaraya göre {adaptive_stats['savings_factor']:.2f}x tasarruf)")

    print("\n6) Girdi verisi çözünürlük tavanı")
    mahalle_ceiling = input_resolution.measure_mahalle_polygon_resolution(session)
    print(f"  {mahalle_ceiling.ceiling_description}")
    vector_notes = input_resolution.point_and_vector_layer_notes()
    unavailable = input_resolution.unavailable_layers_note()
    warnings = input_resolution.resolution_warnings(mahalle_ceiling.effective_linear_resolution_m, resolutions_sorted)
    for w in warnings:
        print(f"  {w}")

    print("\nGrafikler üretiliyor...")
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report.plot_convergence(convergence_metrics, config.CONVERGENCE_MAD_THRESHOLD, config.OUTPUT_DIR / "convergence.png")
    if offset_results:
        report.plot_offset_stability(offset_results, config.MAUP_INSTABILITY_STD_THRESHOLD, config.OUTPUT_DIR / "offset_stability.png")

    markdown = report.generate_markdown_report(
        profile_name=profile.value,
        grid_stats_df=grid_stats_df,
        convergence_metrics=convergence_metrics,
        convergence_resolution_m=convergence_resolution_m,
        mad_threshold=config.CONVERGENCE_MAD_THRESHOLD,
        offset_results=offset_results,
        adaptive_stats=adaptive_stats,
        mahalle_ceiling=mahalle_ceiling,
        vector_layer_notes=vector_notes,
        unavailable_layers=unavailable,
        resolution_warnings=warnings,
    )

    report_path = config.OUTPUT_DIR / "resolution_sensitivity_report.md"
    report_path.write_text(markdown, encoding="utf-8")
    print(f"\nRapor yazıldı: {report_path}")
    return str(report_path)
