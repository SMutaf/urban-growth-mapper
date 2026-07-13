import math
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from app.domain.entities.land_cover import LandCoverCell
from app.domain.entities.point_of_interest import POICategory, PointOfInterest
from app.domain.entities.project import Project, ProjectStatus, ProjectType
from app.domain.entities.road_geometry import RoadGeometry
from app.domain.geo_utils import haversine_distance_km

# Matches "Sakarya 1. Organize Sanayi Bölgesi", "Ferizli OSB",
# "karasu sanayi bölgesi" etc. Individual factories/companies within a zone
# (e.g. "Otokar", "Toyota Otomotiv...") are deliberately excluded - we want
# the organized-settlement zones themselves, not every business in them.
_OSB_NAME_PATTERN = re.compile(r"organize\s+sanayi|(?<!\w)osb(?!\w)|sanayi\s+b[oö]lgesi", re.IGNORECASE)

_KM_PER_LAT_DEGREE = 111.0


def _group_named_ways_by_centroid(elements: List[Dict[str, Any]]) -> Dict[str, tuple]:
    """OSM splits a single named road/railway into many short way segments at
    every intersection. Averaging each name's segment centers into one point
    keeps a "one project = one point" model consistent with the rest of the
    scoring system (many tiny segments would otherwise massively over-weight
    a finely-split road relative to a single POI).
    """
    points_by_name: Dict[str, List[tuple]] = defaultdict(list)
    for element in elements:
        name = element.get("tags", {}).get("name")
        center = element.get("center")
        if not name or not center:
            continue
        points_by_name[name].append((center["lat"], center["lon"]))

    centroids = {}
    for name, points in points_by_name.items():
        avg_lat = sum(p[0] for p in points) / len(points)
        avg_lon = sum(p[1] for p in points) / len(points)
        centroids[name] = (avg_lat, avg_lon)
    return centroids


def extract_highway_projects(elements: List[Dict[str, Any]], city: str) -> List[Project]:
    ways = [e for e in elements if e.get("tags", {}).get("highway") in ("motorway", "trunk")]
    return [
        Project(
            id=None,
            name=name,
            project_type=ProjectType.HIGHWAY,
            status=ProjectStatus.COMPLETED,
            city=city,
            latitude=lat,
            longitude=lon,
            importance=1.0,
            description="OpenStreetMap verisinden otomatik alindi.",
        )
        for name, (lat, lon) in _group_named_ways_by_centroid(ways).items()
    ]


def extract_railway_projects(elements: List[Dict[str, Any]], city: str) -> List[Project]:
    ways = [e for e in elements if e.get("tags", {}).get("railway") == "rail"]
    return [
        Project(
            id=None,
            name=name,
            project_type=ProjectType.RAILWAY,
            status=ProjectStatus.COMPLETED,
            city=city,
            latitude=lat,
            longitude=lon,
            importance=1.0,
            description="OpenStreetMap verisinden otomatik alindi.",
        )
        for name, (lat, lon) in _group_named_ways_by_centroid(ways).items()
    ]


def _group_named_ways_by_geometry(elements: List[Dict[str, Any]]) -> Dict[str, List[List[Tuple[float, float]]]]:
    """Companion to _group_named_ways_by_centroid, for map-display purposes
    instead of scoring: keeps every way segment's full vertex list (queried
    with Overpass's `out geom` rather than `out center`, see
    scripts/ingest_sakarya_road_geometries.py) grouped by road name, instead
    of collapsing them into one averaged point. A named road's segments
    rendered together form one continuous line.
    """
    segments_by_name: Dict[str, List[List[Tuple[float, float]]]] = defaultdict(list)
    for element in elements:
        name = element.get("tags", {}).get("name")
        geometry = element.get("geometry")
        if not name or not geometry:
            continue
        segments_by_name[name].append([(point["lat"], point["lon"]) for point in geometry])
    return segments_by_name


def extract_highway_geometries(elements: List[Dict[str, Any]], city: str) -> List[RoadGeometry]:
    ways = [e for e in elements if e.get("tags", {}).get("highway") in ("motorway", "trunk")]
    return [
        RoadGeometry(id=None, name=name, project_type=ProjectType.HIGHWAY, city=city, segments=segments)
        for name, segments in _group_named_ways_by_geometry(ways).items()
    ]


def extract_railway_geometries(elements: List[Dict[str, Any]], city: str) -> List[RoadGeometry]:
    ways = [e for e in elements if e.get("tags", {}).get("railway") == "rail"]
    return [
        RoadGeometry(id=None, name=name, project_type=ProjectType.RAILWAY, city=city, segments=segments)
        for name, segments in _group_named_ways_by_geometry(ways).items()
    ]


def extract_industrial_zone_projects(elements: List[Dict[str, Any]], city: str) -> List[Project]:
    projects = []
    for element in elements:
        tags = element.get("tags", {})
        name = tags.get("name")
        center = element.get("center")
        if tags.get("landuse") != "industrial" or not name or not center:
            continue
        if not _OSB_NAME_PATTERN.search(name):
            continue
        projects.append(
            Project(
                id=None,
                name=name,
                project_type=ProjectType.INDUSTRIAL_ZONE,
                status=ProjectStatus.COMPLETED,
                city=city,
                latitude=center["lat"],
                longitude=center["lon"],
                importance=1.0,
                description="OpenStreetMap verisinden otomatik alindi.",
            )
        )
    return projects


def extract_port_projects(elements: List[Dict[str, Any]], city: str) -> List[Project]:
    """Matches landuse=harbour features (the actual harbour/port area) -
    deliberately narrower than a generic "Liman" name search, which also
    catches unrelated results (a restaurant named "Liman Lokantasi", small
    fishing/lake piers, a neighbourhood called "Limandere").
    """
    projects = []
    for element in elements:
        tags = element.get("tags", {})
        name = tags.get("name")
        center = element.get("center") or {"lat": element.get("lat"), "lon": element.get("lon")}
        if tags.get("landuse") != "harbour" or not name or center.get("lat") is None:
            continue
        projects.append(
            Project(
                id=None,
                name=name,
                project_type=ProjectType.PORT,
                status=ProjectStatus.UNDER_CONSTRUCTION,
                city=city,
                latitude=center["lat"],
                longitude=center["lon"],
                importance=0.9,
                description="OpenStreetMap verisinden otomatik alindi.",
            )
        )
    return projects


def extract_train_stations(elements: List[Dict[str, Any]], city: str) -> List[PointOfInterest]:
    pois = []
    for element in elements:
        tags = element.get("tags", {})
        if tags.get("railway") != "station":
            continue
        lat = element.get("lat") or (element.get("center") or {}).get("lat")
        lon = element.get("lon") or (element.get("center") or {}).get("lon")
        if lat is None or lon is None:
            continue
        pois.append(
            PointOfInterest(
                id=None,
                name=tags.get("name") or "Tren Istasyonu",
                category=POICategory.TRAIN_STATION,
                status=ProjectStatus.COMPLETED,
                city=city,
                latitude=lat,
                longitude=lon,
                importance=1.0,
            )
        )
    return pois


def extract_highway_junctions(elements: List[Dict[str, Any]], city: str) -> List[PointOfInterest]:
    pois = []
    for element in elements:
        tags = element.get("tags", {})
        if tags.get("highway") != "motorway_junction":
            continue
        lat = element.get("lat") or (element.get("center") or {}).get("lat")
        lon = element.get("lon") or (element.get("center") or {}).get("lon")
        if lat is None or lon is None:
            continue
        pois.append(
            PointOfInterest(
                id=None,
                name=tags.get("name") or tags.get("ref") or "Otoyol Kavsagi",
                category=POICategory.HIGHWAY_JUNCTION,
                status=ProjectStatus.COMPLETED,
                city=city,
                latitude=lat,
                longitude=lon,
                importance=1.0,
            )
        )
    return pois


def extract_universities(elements: List[Dict[str, Any]], city: str) -> List[PointOfInterest]:
    pois = []
    for element in elements:
        tags = element.get("tags", {})
        if tags.get("amenity") != "university":
            continue
        lat = element.get("lat") or (element.get("center") or {}).get("lat")
        lon = element.get("lon") or (element.get("center") or {}).get("lon")
        if lat is None or lon is None:
            continue
        pois.append(
            PointOfInterest(
                id=None,
                name=tags.get("name") or "Universite",
                category=POICategory.UNIVERSITY,
                status=ProjectStatus.COMPLETED,
                city=city,
                latitude=lat,
                longitude=lon,
                importance=1.0,
            )
        )
    return pois


def extract_negative_externalities(elements: List[Dict[str, Any]], city: str) -> List[PointOfInterest]:
    """LULUs (locally unwanted land uses) - see
    domain/scoring/contributors/negative_externality.py for why these get
    their own POI categories instead of folding into POICategory.OTHER.
    Only large/significant grave_yard-tagged cemeteries matter here (most
    Sakarya neighbourhoods have a small local mosque cemetery that isn't a
    meaningful disamenity) - filtering by name/size isn't reliable from OSM
    tags alone, so we accept some noise rather than missing real ones.
    """
    category_by_match = {
        ("amenity", "prison"): POICategory.PRISON,
        ("landuse", "landfill"): POICategory.LANDFILL,
        ("amenity", "grave_yard"): POICategory.CEMETERY,
        ("landuse", "cemetery"): POICategory.CEMETERY,
    }
    default_names = {
        POICategory.PRISON: "Cezaevi",
        POICategory.LANDFILL: "Cop Sahasi",
        POICategory.CEMETERY: "Mezarlik",
    }
    pois = []
    for element in elements:
        tags = element.get("tags", {})
        category = next(
            (cat for (key, value), cat in category_by_match.items() if tags.get(key) == value),
            None,
        )
        if category is None:
            continue
        lat = element.get("lat") or (element.get("center") or {}).get("lat")
        lon = element.get("lon") or (element.get("center") or {}).get("lon")
        if lat is None or lon is None:
            continue
        pois.append(
            PointOfInterest(
                id=None,
                name=tags.get("name") or default_names[category],
                category=category,
                status=ProjectStatus.COMPLETED,
                city=city,
                latitude=lat,
                longitude=lon,
                importance=1.0,
            )
        )
    return pois


def aggregate_land_cover(
    elements: List[Dict[str, Any]],
    lattice_points: List[Tuple[float, float]],
    city: str,
    search_radius_km: float,
) -> List[LandCoverCell]:
    """For FringeContributor (app/domain/scoring/contributors/fringe.py):
    one LandCoverCell per (lat, lon) in `lattice_points` (normally the same
    ~1km grid the production heatmap itself uses - see
    scripts/ingest_sakarya_osm.py), each carrying the count of
    building=* elements within search_radius_km and whether any
    landuse=farmland/meadow/grass element is nearby. This is deliberately
    NOT one row per OSM building (a whole province can have hundreds of
    thousands) - only the local density at each lattice point matters to
    the scoring model, not individual building identity.

    Buildings/open-land elements are bucketed into a coarse spatial index
    first (same technique as ScoringContext's POI bucket index) rather than
    checked against every lattice point directly - a plain O(lattice x
    elements) scan would be tens of millions of haversine calls for a
    province-wide building layer.
    """
    building_points = _element_centers(elements, key="building")
    open_land_points = _element_centers(elements, key="landuse", values={"farmland", "meadow", "grass"})

    bucket_size_km = max(search_radius_km * 2, 0.5)
    building_buckets = _bucket_points(building_points, bucket_size_km)
    open_land_buckets = _bucket_points(open_land_points, bucket_size_km)

    cells = []
    for lat, lon in lattice_points:
        building_count = sum(
            1
            for candidate_lat, candidate_lon in _nearby_bucketed_points(building_buckets, lat, lon, bucket_size_km)
            if haversine_distance_km(lat, lon, candidate_lat, candidate_lon) <= search_radius_km
        )
        has_open_land = any(
            haversine_distance_km(lat, lon, candidate_lat, candidate_lon) <= search_radius_km
            for candidate_lat, candidate_lon in _nearby_bucketed_points(open_land_buckets, lat, lon, bucket_size_km)
        )
        cells.append(
            LandCoverCell(
                id=None, city=city, latitude=lat, longitude=lon,
                building_count=building_count, is_open_land=has_open_land,
            )
        )
    return cells


def _element_centers(
    elements: List[Dict[str, Any]], key: str, values: Optional[set] = None
) -> List[Tuple[float, float]]:
    points = []
    for element in elements:
        tags = element.get("tags", {})
        value = tags.get(key)
        if value is None:
            continue
        if values is not None and value not in values:
            continue
        lat = element.get("lat") or (element.get("center") or {}).get("lat")
        lon = element.get("lon") or (element.get("center") or {}).get("lon")
        if lat is not None and lon is not None:
            points.append((lat, lon))
    return points


def _bucket_key(lat: float, lon: float, bucket_size_km: float) -> Tuple[int, int]:
    lon_km_per_degree = _KM_PER_LAT_DEGREE * math.cos(math.radians(lat))
    return (int(lat * _KM_PER_LAT_DEGREE // bucket_size_km), int(lon * lon_km_per_degree // bucket_size_km))


def _bucket_points(
    points: List[Tuple[float, float]], bucket_size_km: float
) -> Dict[Tuple[int, int], List[Tuple[float, float]]]:
    buckets: Dict[Tuple[int, int], List[Tuple[float, float]]] = defaultdict(list)
    for lat, lon in points:
        buckets[_bucket_key(lat, lon, bucket_size_km)].append((lat, lon))
    return buckets


def _nearby_bucketed_points(
    buckets: Dict[Tuple[int, int], List[Tuple[float, float]]], lat: float, lon: float, bucket_size_km: float
) -> List[Tuple[float, float]]:
    center_i, center_j = _bucket_key(lat, lon, bucket_size_km)
    results = []
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            results.extend(buckets.get((center_i + di, center_j + dj), []))
    return results


def extract_transit_pois(elements: List[Dict[str, Any]], city: str) -> List[PointOfInterest]:
    pois = []
    for element in elements:
        tags = element.get("tags", {})
        is_bus_stop = tags.get("highway") == "bus_stop"
        is_bus_station = tags.get("amenity") == "bus_station"
        if not (is_bus_stop or is_bus_station):
            continue
        lat = element.get("lat") or (element.get("center") or {}).get("lat")
        lon = element.get("lon") or (element.get("center") or {}).get("lon")
        if lat is None or lon is None:
            continue
        pois.append(
            PointOfInterest(
                id=None,
                name=tags.get("name") or ("Otobus Terminali" if is_bus_station else "Otobus Duragi"),
                category=POICategory.BUS_STOP,
                status=ProjectStatus.COMPLETED,
                city=city,
                latitude=lat,
                longitude=lon,
                importance=0.9 if is_bus_station else 0.4,
            )
        )
    return pois
