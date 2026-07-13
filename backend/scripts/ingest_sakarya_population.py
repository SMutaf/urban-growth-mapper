"""Automated ingestion of real Sakarya population/growth data, replacing the
need to hand-enter demographic figures.

Source: veri.sakarya.bel.tr, a public CKAN open-data portal run by Sakarya
Buyuksehir Belediyesi. This script:

1. Discovers every "<district> TOPLAM NUFUS" (total population) dataset via
   the CKAN search API, downloads its XLSX resource, and computes a
   compound annual growth rate (CAGR) per district from the yearly figures.
2. Discovers and downloads the neighbourhood (mahalle) boundary GeoJSON,
   reprojecting it from the source CRS (EPSG:5254) to WGS84 (EPSG:4326) and
   decoding its legacy Turkish text encoding.
3. Joins each mahalle polygon to its district's growth rate (falling back to
   prefix matching for a handful of districts whose names are corrupted by
   inconsistent encoding in the source file - see mahalle_geojson_parser.py)
   and bulk-inserts the result into district_boundaries.

The source server also reliably truncates the boundary file a couple hundred
bytes short of the declared length; we tolerate that and ingest whatever
parsed successfully rather than failing the whole run.

Run with, from the backend/ directory:

    python scripts/ingest_sakarya_population.py
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.infrastructure.ingestion.ckan_client import CkanClient  # noqa: E402
from app.infrastructure.ingestion.mahalle_geojson_parser import (  # noqa: E402
    normalize_district_name,
    parse_mahalle_boundaries,
)
from app.infrastructure.ingestion.population_xlsx_parser import (  # noqa: E402
    compute_growth_rate,
    compute_momentum,
    parse_population_timeseries,
)
from app.infrastructure.persistence.database import SessionLocal  # noqa: E402
from app.infrastructure.persistence.repositories.district_boundary_repository import (  # noqa: E402
    MahalleRecord,
    SqlAlchemyDistrictBoundaryRepository,
)

CKAN_BASE_URL = "https://veri.sakarya.bel.tr"
CITY = "sakarya"

DISTRICT_TITLE_PATTERN = re.compile(
    r"ARASI\s+(.+?)\s+(?:İLÇESİ\s+)?TOPLAM\s+N[ÜU]FUS", re.IGNORECASE
)
MIN_PREFIX_MATCH_LENGTH = 4


def fetch_district_stats(client: CkanClient) -> dict:
    """Returns {normalized_district_name: (growth_rate, momentum, population,
    year)} discovered from every per-district total-population dataset on
    the portal - growth_rate is the CAGR over the full timeseries, momentum
    is the recent-half CAGR minus that (see compute_momentum), population/
    year are the most recent data point.
    """
    stats = {}
    for package in client.search_packages("TOPLAM NUFUS", rows=50):
        match = DISTRICT_TITLE_PATTERN.search(package.get("title", ""))
        if not match:
            continue
        district_name = match.group(1).strip()

        xlsx_resource = next(
            (r for r in package.get("resources", []) if r["url"].lower().endswith(".xlsx")),
            None,
        )
        if xlsx_resource is None:
            continue

        xlsx_bytes = client.download_resource(xlsx_resource["url"])
        try:
            timeseries = parse_population_timeseries(xlsx_bytes)
            growth_rate = compute_growth_rate(timeseries)
            momentum = compute_momentum(timeseries)
        except ValueError as exc:
            print(f"  skip '{district_name}': {exc}")
            continue

        latest_year, latest_population = timeseries[-1]
        stats[normalize_district_name(district_name)] = (
            growth_rate,
            momentum,
            latest_population,
            latest_year,
        )
        print(
            f"  {district_name}: {latest_population:,} ({latest_year}), "
            f"{growth_rate:+.4%}/yil (momentum {momentum:+.4%})"
        )

    return stats


def find_district_stats(district_key: str, stats: dict):
    if district_key in stats:
        return stats[district_key]
    # Fallback: some district names in the boundary file are corrupted by
    # mixed source encoding (see mahalle_geojson_parser.py) and only match
    # the clean population-dataset name as a prefix/suffix of each other.
    for key, value in stats.items():
        if len(district_key) < MIN_PREFIX_MATCH_LENGTH or len(key) < MIN_PREFIX_MATCH_LENGTH:
            continue
        if key.startswith(district_key) or district_key.startswith(key):
            return value
    return None


def fetch_mahalle_boundaries_geojson(client: CkanClient) -> bytes:
    # A multi-word query (e.g. "mahalle sinir") returns zero hits on this
    # portal's search index - a single term works and we filter by resource
    # extension below to pick out the actual boundary dataset.
    for package in client.search_packages("mahalle", rows=10):
        geojson_resource = next(
            (
                r
                for r in package.get("resources", [])
                if r["url"].lower().endswith(".geojson")
            ),
            None,
        )
        if geojson_resource:
            return client.download_resource(geojson_resource["url"])
    raise RuntimeError("Could not find a mahalle boundaries GeoJSON dataset on the portal")


def ingest() -> None:
    client = CkanClient(CKAN_BASE_URL)

    print("Discovering per-district population datasets...")
    stats = fetch_district_stats(client)
    print(f"Found population stats for {len(stats)} districts.\n")

    print("Downloading neighbourhood boundary GeoJSON...")
    raw_geojson = fetch_mahalle_boundaries_geojson(client)

    matched_records = []
    unmatched_districts = set()
    for mahalle in parse_mahalle_boundaries(raw_geojson):
        district_stats = find_district_stats(mahalle.district_name_normalized, stats)
        if district_stats is None:
            unmatched_districts.add(mahalle.district_name)
            continue
        growth_rate, momentum, population, population_year = district_stats
        matched_records.append(
            MahalleRecord(
                district_name=mahalle.district_name,
                growth_rate=growth_rate,
                growth_momentum=momentum,
                population=population,
                population_year=population_year,
                geometry=mahalle.geometry,
            )
        )

    print(f"Matched {len(matched_records)} mahalle polygons to district population stats.")
    if unmatched_districts:
        print(f"Could not match population stats for: {sorted(unmatched_districts)}")

    session = SessionLocal()
    try:
        repo = SqlAlchemyDistrictBoundaryRepository(session)
        repo.clear_city(CITY)
        repo.bulk_insert(CITY, matched_records)
    finally:
        session.close()


if __name__ == "__main__":
    ingest()
    print("\nDone.")
