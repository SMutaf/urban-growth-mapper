from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ProjectType(str, Enum):
    HIGHWAY = "highway"
    RAILWAY = "railway"
    INDUSTRIAL_ZONE = "industrial_zone"
    PORT = "port"
    OTHER = "other"


class ProjectStatus(str, Enum):
    PLANNED = "planned"
    UNDER_CONSTRUCTION = "under_construction"
    COMPLETED = "completed"


@dataclass
class Project:
    id: Optional[int]
    name: str
    project_type: ProjectType
    status: ProjectStatus
    city: str
    latitude: float
    longitude: float
    importance: float = 1.0
    description: str = ""
