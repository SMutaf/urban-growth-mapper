from app.domain.entities.project import ProjectStatus

# Shared between Project and PointOfInterest: a completed piece of
# infrastructure has a more certain effect on growth than a merely planned one.
STATUS_MULTIPLIERS = {
    ProjectStatus.COMPLETED: 1.0,
    ProjectStatus.UNDER_CONSTRUCTION: 0.9,
    ProjectStatus.PLANNED: 0.6,
}
