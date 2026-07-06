from dataclasses import dataclass, field
from typing import List

from app.domain.entities.hazard_zone import HazardZone
from app.domain.entities.point_of_interest import PointOfInterest
from app.domain.entities.project import Project


@dataclass
class ScoringContext:
    """Everything the scoring contributors might read for a given city.

    A single bundle keeps IHeatmapScorer.score_regions from needing a new
    positional argument every time a new factor (flood risk, zoning...) is
    added later - contributors just ignore the fields they don't care about.
    """

    projects: List[Project] = field(default_factory=list)
    points_of_interest: List[PointOfInterest] = field(default_factory=list)
    hazard_zones: List[HazardZone] = field(default_factory=list)
