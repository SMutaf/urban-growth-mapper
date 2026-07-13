from io import BytesIO
from typing import List, Optional, Tuple

import openpyxl

# The source files (Sakarya municipality open data portal) store Turkish text
# labels ("Yıl", "Nüfus") with broken encoding in the XLSX itself, so we don't
# rely on matching those labels - instead we detect the year row (4-digit
# numeric-looking strings) and the population row (plain integers) by shape.
MIN_YEAR = 1900
MAX_YEAR = 2100


def parse_population_timeseries(xlsx_bytes: bytes) -> List[Tuple[int, int]]:
    """Parses a "<district> total population by year" XLSX into
    [(year, population), ...] sorted by year.
    """
    workbook = openpyxl.load_workbook(BytesIO(xlsx_bytes), data_only=True)
    sheet = workbook.active

    years: List[int] = []
    populations: List[int] = []

    for row in sheet.iter_rows(values_only=True):
        year_like = _extract_years(row)
        if year_like and not years:
            years = year_like
            continue
        if years and not populations:
            population_like = _extract_populations(row, expected_count=len(years))
            if population_like:
                populations = population_like

    if not years or not populations or len(years) != len(populations):
        raise ValueError("Could not locate a matching year/population row pair in the XLSX sheet")

    return sorted(zip(years, populations))


def _extract_years(row: tuple) -> List[int]:
    values = []
    for cell in row:
        if isinstance(cell, str) and cell.strip().isdigit():
            year = int(cell.strip())
            if MIN_YEAR <= year <= MAX_YEAR:
                values.append(year)
    return values if len(values) >= 2 else []


def _extract_populations(row: tuple, expected_count: int) -> List[int]:
    values = [v for v in (_coerce_population(cell) for cell in row) if v is not None]
    return values if len(values) == expected_count else []


def _coerce_population(cell) -> Optional[int]:
    if isinstance(cell, int):
        return cell if cell > 1000 else None
    if isinstance(cell, str):
        # Source data occasionally has stray whitespace/typos around a
        # thousands separator dot, e.g. "90 .855" for 90855 (seen in the
        # Erenler district file) - strip both before parsing.
        cleaned = cell.replace(" ", "").replace(".", "")
        if cleaned.isdigit():
            value = int(cleaned)
            return value if value > 1000 else None
    return None


def compute_growth_rate(timeseries: List[Tuple[int, int]]) -> float:
    """Compound annual growth rate (CAGR) between the first and last data point."""
    if len(timeseries) < 2:
        raise ValueError("Need at least two data points to compute a growth rate")
    return _cagr(timeseries[0], timeseries[-1])


def compute_momentum(timeseries: List[Tuple[int, int]]) -> float:
    """Recent-half CAGR minus whole-series CAGR: positive means growth has
    been accelerating lately relative to the district's own longer-run
    average (a "coming up" signal), negative means it's decelerating (was
    hot, has since cooled) - a flat CAGR alone can't distinguish the two,
    which is exactly the "already fully grown" vs "growing right now"
    ambiguity a growth-direction heatmap needs to resolve. Needs at least 4
    points so the recent half is itself at least 2 points; shorter series
    return 0.0 (no basis for a momentum read yet).
    """
    if len(timeseries) < 4:
        return 0.0
    overall_rate = _cagr(timeseries[0], timeseries[-1])
    recent_half = timeseries[len(timeseries) // 2 :]
    recent_rate = _cagr(recent_half[0], recent_half[-1])
    return recent_rate - overall_rate


def _cagr(start: Tuple[int, int], end: Tuple[int, int]) -> float:
    start_year, start_population = start
    end_year, end_population = end
    years_elapsed = end_year - start_year
    if years_elapsed <= 0 or start_population <= 0:
        raise ValueError("Invalid timeseries for CAGR computation")
    return (end_population / start_population) ** (1 / years_elapsed) - 1
