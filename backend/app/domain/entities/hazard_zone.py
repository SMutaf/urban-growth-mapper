from dataclasses import dataclass
from enum import Enum
from typing import Optional


class HazardType(str, Enum):
    EARTHQUAKE = "earthquake"
    FLOOD = "flood"


@dataclass
class HazardZone:
    id: Optional[int]
    name: str
    hazard_type: HazardType
    risk_level: float  # 0.0 (negligible) .. 1.0 (severe)
    city: str
    latitude: float
    longitude: float
