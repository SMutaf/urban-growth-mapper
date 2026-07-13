"""Derives FringeContributor's building-density inverted-U breakpoints from
the real distribution of building density across the city, rather than
guessing absolute building-count thresholds (a hardcoded "50 buildings ="
some fixed judgment would be meaningless without knowing what's actually
typical for Sakarya vs another city). Same pattern as
growth_direction_analysis.compute_sector_growth: a pure function computed
once from city-wide data by HeatmapService and injected into
ScoringContext, not something a contributor computes itself (contributors
are pure functions with no DB access).

Pure Python (no numpy) - the domain layer has no third-party dependencies,
same rule that keeps geo_utils.py plain math instead of numpy.
"""

from typing import List

from app.domain.scoring.band_function import BandFunction


def _percentile(sorted_values: List[float], fraction: float) -> float:
    """Linear-interpolation percentile (same convention as numpy's default
    'linear' method) over an already-sorted list.
    """
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = fraction * (len(sorted_values) - 1)
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    t = position - lower
    return sorted_values[lower] + t * (sorted_values[upper] - sorted_values[lower])


def compute_density_band(
    building_counts: List[int], min_multiplier: float, max_multiplier: float
) -> BandFunction:
    """Inverted-U over the real building-density distribution: zero-
    building (pure rural/undeveloped) cells score at the floor
    (min_multiplier); the peri-urban transition zone - neither raw
    countryside nor a filled-in neighbourhood - peaks at max_multiplier;
    already-built-out/saturated cells fall back to the floor.

    The rising/peak/falling shoulders (25th/50th/75th percentile) are
    computed over the NONZERO subset only, not the whole city - most 1km
    cells in a real province are pure countryside (Sakarya: >80% of
    lattice cells have zero buildings), so including all the zeros would
    make p0 through p50+ all collapse to 0 and strand the inverted-U's
    peak behind several zero-width segments that banded_value's point
    lookup can never actually reach (its first check intercepts any query
    at or below the first breakpoint before the later, real segments are
    even considered - see band_function.py). Splitting "is there any
    building here at all" (binary, floor vs. not) from "how built-up is it
    given that there's something here" (the percentile shape) avoids that
    collapse regardless of how skewed the real distribution is.

    Returns an empty list (banded_value's caller convention: treat as "no
    signal, stay neutral") if there's no land cover data yet, or if every
    ingested cell has zero buildings (nothing to peak towards - every cell
    would be equally undeveloped, so there's no real fringe distinction to
    draw yet).
    """
    if not building_counts:
        return []
    nonzero = sorted(float(c) for c in building_counts if c > 0)
    if not nonzero:
        return []

    p25 = _percentile(nonzero, 0.25)
    p50 = _percentile(nonzero, 0.50)
    p75 = _percentile(nonzero, 0.75)
    p100 = nonzero[-1]

    band: BandFunction = [
        (0.0, min_multiplier),
        (p25, 1.0),
        (p50, max_multiplier),
        (p75, 1.0),
        (p100, min_multiplier),
    ]
    return _ensure_strictly_increasing_x(band)


def _ensure_strictly_increasing_x(band: BandFunction) -> BandFunction:
    """Even restricted to the nonzero subset, percentiles of a real, heavily
    skewed distribution can still collide (e.g. if most nonzero cells
    cluster at the same low count) - nudge any duplicate/out-of-order x by
    a negligible epsilon so every breakpoint stays individually reachable
    without changing its intended value or meaningfully changing where it
    kicks in (building counts are integers; 1e-6 is far below that
    resolution).
    """
    result = [band[0]]
    for x, v in band[1:]:
        prev_x = result[-1][0]
        if x <= prev_x:
            x = prev_x + 1e-6
        result.append((x, v))
    return result
