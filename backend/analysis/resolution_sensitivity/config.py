"""Shared constants for the resolution sensitivity analysis pipeline.

CRS NOTE (deliberate deviation from the original spec): the task asked for
EPSG:5256, but that CRS (TUREF / TM36) is only valid for 34.5-37.5 degrees
East - eastern Turkey. Sakarya sits at ~29.97-31.01 degrees East, well
outside that zone, so projecting into it would introduce real, avoidable
distortion into every distance/area computation in this pipeline. EPSG:5254
(TUREF / TM30, valid 28.5-31.5 degrees East) is the correct zone for this
location, and is also the CRS this codebase already uses for Sakarya's
mahalle boundary data (see infrastructure/ingestion/mahalle_geojson_parser.py)
- using it here keeps the whole project on one consistent, actually-correct
projection for this region.
"""

from pathlib import Path

CITY = "sakarya"

CRS_METRIC = "EPSG:5254"  # TUREF / TM30 - correct zone for Sakarya's longitude
CRS_GEOGRAPHIC = "EPSG:4326"  # WGS84 - what the production scoring pipeline uses

# Coarse-to-fine ladder. 100m is ~100x the cell count of 1000m (per the
# task's own estimate) and is opt-in at the CLI level (see
# scripts/run_resolution_sensitivity_analysis.py --include-100m) because a
# full-grid score at that count can take tens of minutes in pure Python -
# see scoring.py's calibration step, which prints a real measured estimate
# before committing to the run rather than guessing blind.
RESOLUTIONS_M = [1000, 500, 250, 100]
DEFAULT_RESOLUTIONS_M = [1000, 500, 250]

# Below this MAD (on the 0-1 normalized score scale), refining further is
# judged to not meaningfully change the result - see convergence.py. This
# is a judgment threshold, not derived from data; 0.02 was specified in the
# task itself.
CONVERGENCE_MAD_THRESHOLD = 0.02

# Grid origin shifts tested per resolution, as a fraction of cell size, in
# both the northing and easting direction - see maup_offset.py.
MAUP_OFFSET_FRACTIONS = [0.0, 0.25, 0.5, 0.75]

# A resolution is flagged unstable (offset-dependent, i.e. the grid itself
# rather than the underlying data is driving the result) if a probe
# point's raw_score coefficient of variation (std/mean) across offsets
# exceeds this - e.g. 0.05 means "the score swings more than ~5% just from
# where the grid happens to start, with nothing about the real location
# having changed". Coefficient of variation, not raw std, because
# raw_score's absolute scale varies a lot cell to cell - see
# maup_offset.py.
MAUP_INSTABILITY_STD_THRESHOLD = 0.05

# Fixed set of probe points reused across every resolution and every MAUP
# offset variant, so convergence/offset comparisons are apples-to-apples
# and don't scale with the full grid's cell count (see scoring.py).
PROBE_SAMPLE_SIZE = 3000
RANDOM_SEED = 42

# Adaptive grid (see adaptive_grid.py): start at the coarsest rung of
# RESOLUTIONS_M and recursively split a cell in four while it is "hot" or
# heterogeneous, down to a floor of this size.
ADAPTIVE_COARSE_M = 1000
ADAPTIVE_FINE_FLOOR_M = 250
# A cell is "hot" if its score is at/above this percentile of the coarse
# grid's own score distribution.
ADAPTIVE_HOT_SCORE_PERCENTILE = 0.75
# A cell is "heterogeneous" (an expansion-front candidate) if its score
# differs from the mean of its orthogonal neighbours by more than this.
ADAPTIVE_HETEROGENEITY_THRESHOLD = 0.15
# A cell is also split if within this distance (metres) of a university,
# OSB, or highway junction - independent infrastructure signals for an
# active growth front, on top of the score-based rules above. (TOKİ /
# imar-değişim zone data mentioned in the original task brief doesn't
# exist in this project - see report.py's input-resolution-ceiling section
# for what data we do and don't have.)
ADAPTIVE_INFRA_BUFFER_M = 2000

BACKEND_DIR = Path(__file__).resolve().parents[2]
CITY_BOUNDARY_GEOJSON = BACKEND_DIR / "app" / "core" / "data" / "sakarya_boundary.geojson"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
