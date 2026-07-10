from app.domain.entities.project import ProjectType
from app.domain.entities.region import Region
from app.domain.geo_utils import haversine_distance_km
from app.domain.scoring.scoring_context import ScoringContext
from app.domain.scoring.status_weights import STATUS_MULTIPLIERS

# Railway, highway, and industrial_zone project types are deliberately
# excluded here - the hedonic-pricing literature calls for non-monotonic,
# banded distance curves for those (see RailwayNoiseContributor +
# RailStationAccessContributor, HighwayNoiseContributor +
# HighwayJunctionAccessContributor, IndustrialZoneAccessContributor), which
# a plain inverse-distance-decay formula can't express. Including them here
# too would double-count the same underlying Project rows.
PROJECT_TYPE_WEIGHTS = {
    ProjectType.PORT: 0.9,
    ProjectType.OTHER: 0.5,
}


class ProjectProximityContributor:
    """Positive factor for project types with no specialized banded
    contributor (currently: port, other) - sum of (type weight x status
    weight x importance), decayed by inverse distance.
    """

    def contribute(self, region: Region, context: ScoringContext) -> float:
        total = 0.0
        for project in context.projects:
            if project.project_type not in PROJECT_TYPE_WEIGHTS:
                continue
            distance_km = haversine_distance_km(
                region.center_lat, region.center_lon, project.latitude, project.longitude
            )
            type_weight = PROJECT_TYPE_WEIGHTS[project.project_type]
            status_weight = STATUS_MULTIPLIERS.get(project.status, 0.6)
            total += (type_weight * status_weight * project.importance) / (1 + distance_km)
        return total
