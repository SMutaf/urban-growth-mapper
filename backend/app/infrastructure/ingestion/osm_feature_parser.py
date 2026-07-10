import re
from collections import defaultdict
from typing import Any, Dict, List

from app.domain.entities.point_of_interest import POICategory, PointOfInterest
from app.domain.entities.project import Project, ProjectStatus, ProjectType

# Matches "Sakarya 1. Organize Sanayi Bölgesi", "Ferizli OSB",
# "karasu sanayi bölgesi" etc. Individual factories/companies within a zone
# (e.g. "Otokar", "Toyota Otomotiv...") are deliberately excluded - we want
# the organized-settlement zones themselves, not every business in them.
_OSB_NAME_PATTERN = re.compile(r"organize\s+sanayi|(?<!\w)osb(?!\w)|sanayi\s+b[oö]lgesi", re.IGNORECASE)


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
