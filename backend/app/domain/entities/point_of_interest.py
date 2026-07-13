from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.domain.entities.project import ProjectStatus


class POICategory(str, Enum):
    METRO_STATION = "metro_station"
    TRAIN_STATION = "train_station"
    HIGHWAY_JUNCTION = "highway_junction"
    UNIVERSITY = "university"
    BUS_STOP = "bus_stop"
    HOSPITAL = "hospital"
    SHOPPING_CENTER = "shopping_center"
    SCHOOL = "school"
    CITY_CENTER = "city_center"
    OTHER = "other"
    # LULU (locally unwanted land use) categories - hedonic-pricing literature
    # consistently finds these among the strongest negative price effects,
    # see NegativeExternalityContributor.
    PRISON = "prison"
    LANDFILL = "landfill"
    CEMETERY = "cemetery"


@dataclass
class PointOfInterest:
    id: Optional[int]
    name: str
    category: POICategory
    # Reused from Project: a planned-but-not-yet-built metro/bus stop already
    # boosts nearby land value, same as an infrastructure project would.
    status: ProjectStatus
    city: str
    latitude: float
    longitude: float
    importance: float = 1.0
