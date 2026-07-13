from app.domain.scoring.band_function import banded_value
from app.domain.scoring.fringe_density_band import compute_density_band


def test_empty_input_yields_empty_band():
    assert compute_density_band([], 0.85, 1.20) == []


def test_all_zero_input_yields_empty_band():
    # No built-up cells anywhere - nothing to peak towards, every cell is
    # equally undeveloped, so there's no real fringe distinction to draw.
    assert compute_density_band([0, 0, 0, 0], 0.85, 1.20) == []


def test_median_nonzero_density_peaks():
    counts = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    band = compute_density_band(counts, min_multiplier=0.85, max_multiplier=1.20)

    peak_x = band[2][0]  # the band's own recorded median-of-nonzero breakpoint
    peak_value = banded_value(peak_x, band)
    empty_value = banded_value(0, band)
    saturated_value = banded_value(100, band)

    assert peak_value == 1.20
    assert empty_value == 0.85
    assert saturated_value == 0.85
    assert peak_value > empty_value
    assert peak_value > saturated_value


def test_moderate_density_scores_between_floor_and_peak():
    counts = list(range(0, 101, 5))
    band = compute_density_band(counts, min_multiplier=0.85, max_multiplier=1.20)

    # Halfway between the rising-shoulder breakpoint and the peak - should
    # land strictly between the floor and the peak.
    rising_x, peak_x = band[1][0], band[2][0]
    midpoint_value = banded_value((rising_x + peak_x) / 2, band)
    assert 0.85 < midpoint_value < 1.20


def test_single_distinct_nonzero_value_does_not_crash():
    band = compute_density_band([0, 42, 42, 42, 42], min_multiplier=0.85, max_multiplier=1.20)
    # All nonzero breakpoints collapse to x=42 - _ensure_strictly_increasing_x
    # must nudge them apart rather than raising or silently losing the peak.
    peak_x = band[2][0]
    assert banded_value(peak_x, band) == 1.20
    assert banded_value(0, band) == 0.85


def test_heavily_skewed_real_world_shape_still_reaches_peak():
    # Mirrors Sakarya's real distribution: the vast majority of cells have
    # zero buildings, only a minority are built up at all. This is exactly
    # the shape that used to collapse the inverted-U into an unreachable
    # peak (see fringe_density_band.py's module docstring).
    counts = [0] * 900 + [1, 1, 1, 2, 2, 5, 10, 20, 50, 100, 500, 1700]
    band = compute_density_band(counts, min_multiplier=0.85, max_multiplier=1.20)

    peak_x = band[2][0]
    assert banded_value(peak_x, band) == 1.20
    assert banded_value(0, band) == 0.85
    # A small positive count (well below the peak) should score above the
    # floor - proving the rising shoulder is reachable, not stranded.
    assert banded_value(1, band) > 0.85
