"""One-time data-quality audit: cross-checks our OSM/municipality-sourced
POIs (cemeteries, hospitals, train/bus stations) and the single city-center
point against Google Places API (New) and the Geocoding API, to catch
gaps or mistakes without re-deriving anything - this is a read-only
diagnostic, it never writes to the database.

Scope, and why it's scoped this way:
- Cemeteries & hospitals: Places API's `searchNearby` has a real "cemetery"
  and "hospital" type, so we can ask Google "what do you know about in this
  area" and compare against our own points - a genuine completeness check.
- Bus stops: deliberately NOT audited here. Google Places has no per-stop
  transit type for individual curb-side stops (only "bus_station" for
  terminals) - our 2662 bus stops come from Sakarya's own transit API
  (see ingest_sakarya_bus_stops.py), which is already the authoritative
  source for stop-level detail; Places can only sanity-check that major
  terminals aren't missing, which this script does via bus_station/
  train_station types.
- Roads/highways: NOT audited here. Places is POI-focused, not a road
  network dataset - there's no meaningful Places API call that validates
  OSM motorway/trunk coverage. Left out rather than forcing an irrelevant
  check.
- City center: a single point, verified via the Geocoding API instead of
  Places (cheaper, and it's exactly the "address/place name -> coordinate"
  use case Geocoding is for).

Requires GOOGLE_GEOCODING_API_KEY in backend/.env, with "Places API (New)"
and "Geocoding API" both enabled for that key in Google Cloud Console.

Run with, from the backend/ directory:

    python scripts/audit_pois_with_google_places.py
"""

import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")  # Windows console default (cp1254) can't encode combining
# Turkish characters some Google results come back with (e.g. dotted/dotless i variants) - this script
# is print-only diagnostics, so redirecting stdout encoding is simpler than transliterating every string.

from app.core.city_bounds import load_city_boundary  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.domain.entities.point_of_interest import POICategory  # noqa: E402
from app.domain.geo_utils import haversine_distance_km, point_in_polygon  # noqa: E402
from app.infrastructure.persistence.database import SessionLocal  # noqa: E402
from app.infrastructure.persistence.repositories.point_of_interest_repository import (  # noqa: E402
    SqlAlchemyPointOfInterestRepository,
)
from sqlalchemy import text  # noqa: E402

CITY = "sakarya"
PLACES_URL = "https://places.googleapis.com/v1/places:searchNearby"
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
REQUEST_DELAY_SECONDS = 0.2

# Places results further than this from every one of our own points are
# flagged as a possible gap in our OSM/municipality data - not a hard
# error, since Google's own POI placement can be off by a similar margin.
GAP_THRESHOLD_KM = 1.0

DISTRICT_SWEEP_RADIUS_M = 20000.0  # within Places' 50km max; districts overlap a bit, results are deduped


def district_centroids(session) -> List[Tuple[str, float, float]]:
    """One representative point per ilce - the average of that ilce's
    mahalle centroids (from district_boundaries, ingested by
    ingest_sakarya_population.py). Good enough as a Places sweep center;
    we don't need the exact town-hall coordinate, just something within
    DISTRICT_SWEEP_RADIUS_M of everything in that district.
    """
    rows = session.execute(text("""
        SELECT district_name, AVG(ST_Y(ST_Centroid(boundary))), AVG(ST_X(ST_Centroid(boundary)))
        FROM district_boundaries
        GROUP BY district_name
        ORDER BY district_name
    """)).fetchall()
    return [(name, lat, lon) for name, lat, lon in rows]


def places_nearby(api_key: str, lat: float, lon: float, radius_m: float, included_types: List[str]) -> List[dict]:
    response = requests.post(
        PLACES_URL,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            # Basic Data tier only (displayName, location) - keeps this
            # province-wide sweep cheap; formattedAddress is fetched
            # separately, only for the handful of spot-checks that need it.
            "X-Goog-FieldMask": "places.displayName,places.location",
        },
        json={
            "includedTypes": included_types,
            "maxResultCount": 20,
            "locationRestriction": {"circle": {"center": {"latitude": lat, "longitude": lon}, "radius": radius_m}},
        },
        timeout=15,
    )
    response.raise_for_status()
    return response.json().get("places", [])


def places_nearby_with_address(api_key: str, lat: float, lon: float, radius_m: float, included_types: List[str]) -> List[dict]:
    response = requests.post(
        PLACES_URL,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "places.displayName,places.location,places.formattedAddress",
        },
        json={
            "includedTypes": included_types,
            "maxResultCount": 5,
            "locationRestriction": {"circle": {"center": {"latitude": lat, "longitude": lon}, "radius": radius_m}},
        },
        timeout=15,
    )
    response.raise_for_status()
    return response.json().get("places", [])


def geocode(api_key: str, address: str) -> Optional[Tuple[float, float]]:
    response = requests.get(GEOCODE_URL, params={"address": address, "key": api_key, "region": "tr"}, timeout=15)
    response.raise_for_status()
    data = response.json()
    if data.get("status") != "OK" or not data.get("results"):
        return None
    location = data["results"][0]["geometry"]["location"]
    return location["lat"], location["lng"]


def dedupe_places(all_places: List[dict]) -> List[Tuple[str, float, float]]:
    """Sweeping overlapping district circles finds the same real-world
    place more than once - collapse anything within 100m of an
    already-kept point rather than reporting it as two separate gaps.
    """
    kept: List[Tuple[str, float, float]] = []
    for place in all_places:
        name = place.get("displayName", {}).get("text", "?")
        loc = place.get("location", {})
        lat, lon = loc.get("latitude"), loc.get("longitude")
        if lat is None or lon is None:
            continue
        if any(haversine_distance_km(lat, lon, klat, klon) < 0.1 for _, klat, klon in kept):
            continue
        kept.append((name, lat, lon))
    return kept


def audit_category(
    api_key: str, districts: List[Tuple[str, float, float]], included_types: List[str],
    our_points: List[Tuple[float, float]], label: str, boundary: Optional[List[Tuple[float, float]]],
) -> None:
    print(f"\n=== {label} ===")
    print(f"Bizim veritabanimizda: {len(our_points)} nokta.")

    all_places: List[dict] = []
    for district_name, lat, lon in districts:
        try:
            all_places.extend(places_nearby(api_key, lat, lon, DISTRICT_SWEEP_RADIUS_M, included_types))
        except requests.RequestException as exc:
            print(f"  UYARI: {district_name} bolgesi taranamadi: {exc}")
        time.sleep(REQUEST_DELAY_SECONDS)

    google_points_raw = dedupe_places(all_places)
    # The 20km sweep radius around border districts spills into Duzce/
    # Bilecik/Kocaeli - without this filter, hospitals/cemeteries that are
    # real and correct but simply outside Sakarya get reported as "missing
    # Sakarya data", which they aren't.
    if boundary:
        google_points = [(n, lat, lon) for n, lat, lon in google_points_raw if point_in_polygon(lon, lat, boundary)]
        excluded = len(google_points_raw) - len(google_points)
        print(f"Google Places'ta bulunan (tekillestirilmis, Sakarya siniri disi {excluded} sonuc elendi): {len(google_points)} nokta.")
    else:
        google_points = google_points_raw
        print(f"Google Places'ta bulunan (tekillestirilmis): {len(google_points)} nokta.")

    gaps = []
    for name, lat, lon in google_points:
        if not our_points:
            gaps.append((name, lat, lon, None))
            continue
        nearest_km = min(haversine_distance_km(lat, lon, olat, olon) for olat, olon in our_points)
        if nearest_km > GAP_THRESHOLD_KM:
            gaps.append((name, lat, lon, nearest_km))

    if gaps:
        print(f"Olasi EKSIK (bizim veride {GAP_THRESHOLD_KM}km icinde karsiligi yok, Google'da var):")
        for name, lat, lon, nearest_km in sorted(gaps, key=lambda g: -(g[3] or 0)):
            print(f"  - {name} ({lat:.5f}, {lon:.5f}) - en yakin bizim nokta {nearest_km:.2f}km uzakta" if nearest_km else f"  - {name} ({lat:.5f}, {lon:.5f}) - bizde bu kategoride hic nokta yok")
    else:
        print("Google'in bildigi hicbir nokta bizim verimizden 1km'den uzak degil - eksik gorunmuyor.")


def audit_hospital_duplicates(api_key: str, our_hospitals: List[Tuple[str, float, float]]) -> None:
    print("\n=== Hastane kopya-kayit kontrolu ===")
    by_name: Dict[str, List[Tuple[str, float, float]]] = {}
    for name, lat, lon in our_hospitals:
        by_name.setdefault(name, []).append((name, lat, lon))

    for name, points in by_name.items():
        if len(points) < 2:
            continue
        print(f"\n'{name}' - {len(points)} kayit bizim veritabanimizda:")
        for _, lat, lon in points:
            try:
                results = places_nearby_with_address(api_key, lat, lon, 150.0, ["hospital"])
            except requests.RequestException as exc:
                print(f"  ({lat:.5f}, {lon:.5f}) - Places sorgusu basarisiz: {exc}")
                continue
            time.sleep(REQUEST_DELAY_SECONDS)
            if not results:
                print(f"  ({lat:.5f}, {lon:.5f}) - Google bu noktada 150m icinde hastane bulamadi.")
                continue
            top = results[0]
            top_name = top.get("displayName", {}).get("text", "?")
            top_address = top.get("formattedAddress", "?")
            print(f"  ({lat:.5f}, {lon:.5f}) -> Google: '{top_name}' | {top_address}")


def audit_city_center(api_key: str, stored_lat: float, stored_lon: float) -> None:
    print("\n=== Sehir merkezi kontrolu ===")
    print(f"Bizim kayitli noktamiz: ({stored_lat}, {stored_lon})")
    for query in ["Adapazari, Sakarya, Turkiye", "Sakarya sehir merkezi, Turkiye"]:
        result = geocode(api_key, query)
        time.sleep(REQUEST_DELAY_SECONDS)
        if result is None:
            print(f"  '{query}' -> Geocoding sonuc bulamadi.")
            continue
        lat, lon = result
        distance_km = haversine_distance_km(stored_lat, stored_lon, lat, lon)
        print(f"  '{query}' -> Google: ({lat:.5f}, {lon:.5f}) | bizim noktamizdan {distance_km:.2f}km uzakta")


def main() -> None:
    settings = get_settings()
    if not settings.google_geocoding_api_key:
        raise RuntimeError("GOOGLE_GEOCODING_API_KEY is not set in backend/.env")
    api_key = settings.google_geocoding_api_key

    session = SessionLocal()
    try:
        districts = district_centroids(session)
        print(f"{len(districts)} ilce merkezi uzerinden taranacak.")

        poi_repo = SqlAlchemyPointOfInterestRepository(session)
        pois = poi_repo.list_by_city(CITY)

        cemeteries = [(p.latitude, p.longitude) for p in pois if p.category == POICategory.CEMETERY]
        hospitals = [(p.name, p.latitude, p.longitude) for p in pois if p.category == POICategory.HOSPITAL]
        train_stations = [(p.latitude, p.longitude) for p in pois if p.category == POICategory.TRAIN_STATION]
        city_center = next((p for p in pois if p.category == POICategory.CITY_CENTER), None)
        boundary = load_city_boundary(CITY)

        audit_category(api_key, districts, ["cemetery"], cemeteries, "Mezarliklar", boundary)
        audit_category(api_key, districts, ["hospital"], [(lat, lon) for _, lat, lon in hospitals], "Hastaneler", boundary)
        audit_category(api_key, districts, ["bus_station", "train_station"], train_stations, "Ana ulasim terminalleri (durak degil)", boundary)
        audit_hospital_duplicates(api_key, hospitals)
        if city_center:
            audit_city_center(api_key, city_center.latitude, city_center.longitude)
        else:
            print("\nUYARI: veritabaninda city_center kategorisinde nokta yok.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
    print("\nBitti.")
