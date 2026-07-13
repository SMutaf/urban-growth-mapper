from dataclasses import dataclass
from typing import List, Optional, Tuple

from app.domain.entities.project import ProjectType


@dataclass
class RoadGeometry:
    """The real line shape of a named highway/railway, for map display only.

    Deliberately separate from Project (app/domain/entities/project.py),
    which stores one averaged centroid point per named road for scoring
    (see osm_feature_parser._group_named_ways_by_centroid) - contributors
    depend on that "one project = one point" model and must not change.
    This entity carries the full geometry instead: OSM splits a named road
    into many way segments at intersections, so `segments` is a list of
    those segments, each a list of (lat, lon) vertices in path order -
    together they render as one continuous line (a MultiLineString).
    """

    id: Optional[int]
    name: str
    project_type: ProjectType
    city: str
    segments: List[List[Tuple[float, float]]]
