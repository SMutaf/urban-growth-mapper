from dataclasses import dataclass
from typing import Optional


@dataclass
class Region:
    id: Optional[int]
    name: str
    city: str
    center_lat: float
    center_lon: float
