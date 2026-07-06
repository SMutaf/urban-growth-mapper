from app.domain.entities.project import ProjectType
from app.domain.entities.region import Region
from app.domain.geo_utils import haversine_distance_km
from app.domain.scoring.scoring_context import ScoringContext
from app.domain.scoring.status_weights import STATUS_MULTIPLIERS

# Relative importance of each infrastructure project type in the growth score.
PROJECT_TYPE_WEIGHTS = {
    ProjectType.RAILWAY: 1.0,
    ProjectType.PORT: 0.9,
    ProjectType.HIGHWAY: 0.8,
    ProjectType.INDUSTRIAL_ZONE: 0.7,
    ProjectType.OTHER: 0.5,
}


class ProjectProximityContributor:
    """Positive factor: sum of every major infrastructure project's
    (type weight x status weight x importance), decayed by inverse distance.
    """

    def contribute(self, region: Region, context: ScoringContext) -> float:
        total = 0.0
        for project in context.projects:
            distance_km = haversine_distance_km(
                region.center_lat, region.center_lon, project.latitude, project.longitude
            )
            type_weight = PROJECT_TYPE_WEIGHTS.get(project.project_type, 0.5)
            status_weight = STATUS_MULTIPLIERS.get(project.status, 0.6)
            total += (type_weight * status_weight * project.importance) / (1 + distance_km)
        return total
