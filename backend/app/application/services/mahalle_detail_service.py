from typing import Callable, List

from app.application.services.heatmap_service import HeatmapService
from app.domain.entities.land_use_profile import LandUseProfile
from app.infrastructure.persistence.repositories.district_boundary_repository import (
    MahalleScoreEntry,
    SqlAlchemyDistrictBoundaryRepository,
)


class MahalleDetailService:
    """Typed directly against the concrete PostGIS repository, same
    reasoning as DistrictService: exporting a mahalle-level score ranking
    for map display is a read/visualization concern, not a domain use case.

    Deliberately reuses HeatmapService.generate_heatmap's full-city grid
    rather than scoring only the requested district - normalize_scores()
    (see domain/scoring/normalization.py) needs the whole city's batch of
    regions to produce comparable relative scores, the same reason
    HeatmapService.score_point_with_context scores an ad-hoc point
    alongside the full grid instead of alone.
    """

    def __init__(
        self,
        district_repo: SqlAlchemyDistrictBoundaryRepository,
        heatmap_service_factory: Callable[[LandUseProfile], HeatmapService],
    ):
        self._district_repo = district_repo
        self._heatmap_service_factory = heatmap_service_factory

    def get_mahalle_score_ranking(
        self, city: str, district_name: str, profile: LandUseProfile = LandUseProfile.BALANCED
    ) -> List[MahalleScoreEntry]:
        heatmap_service = self._heatmap_service_factory(profile)
        result = heatmap_service.generate_heatmap(city)
        scored_points = [(p.center_lat, p.center_lon, p.score) for p in result.points]
        return self._district_repo.group_scores_by_mahalle(city, district_name, scored_points)
