import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from app.domain.entities.hazard_zone import HazardZone
from app.domain.entities.land_cover import LandCoverCell
from app.domain.entities.point_of_interest import PointOfInterest, POICategory
from app.domain.entities.project import Project, ProjectType
from app.domain.geo_utils import KM_PER_LAT_DEGREE
from app.domain.scoring.band_function import BandFunction

# Grid cell size for the POI spatial bucket index (see pois_near). Small
# enough to meaningfully narrow down "which POIs might be near this region"
# for contributors like PoiProximityContributor that scan thousands of POIs
# per region, large enough to keep the bucket count (and per-lookup
# neighbourhood scan) small.
POI_BUCKET_SIZE_KM = 3.0

# Same idea, for the land-cover density bucket index (see land_cover_near) -
# land cover cells already sit on a ~1km lattice (see
# scripts/ingest_sakarya_osm.py), so a slightly larger bucket keeps each
# bucket's occupancy reasonable without the neighbourhood scan spanning too
# many buckets.
LAND_COVER_BUCKET_SIZE_KM = 3.0


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
    # region_id -> population growth rate of the district containing that
    # region. Precomputed by HeatmapService (a spatial lookup, not a plain
    # list) since contributors are pure functions with no DB access.
    region_growth_rates: Dict[int, float] = field(default_factory=dict)
    # region_id -> growth momentum (recent-half CAGR minus whole-series CAGR)
    # of the district containing that region - see
    # population_xlsx_parser.compute_momentum for what this measures and why.
    region_growth_momentum: Dict[int, float] = field(default_factory=dict)
    # Weighted-average growth rate per 8-way compass sector (index 0 = N,
    # clockwise), relative to the city's overall average - see
    # domain/scoring/growth_direction.py. Precomputed by HeatmapService since
    # it requires all mahalle centroids, not just the ones a given region
    # falls inside.
    growth_direction_sectors: List[float] = field(default_factory=list)
    # Pre-aggregated building-density readings across the city - see
    # app/domain/entities/land_cover.py and FringeContributor
    # (app/domain/scoring/contributors/fringe.py), which is the only
    # consumer of this and fringe_density_band below.
    land_cover_cells: List[LandCoverCell] = field(default_factory=list)
    # Inverted-U breakpoints derived from this city's real building-density
    # distribution (see domain/scoring/fringe_density_band.py) - precomputed
    # by HeatmapService, same reasoning as growth_direction_sectors: this
    # needs the full city-wide density distribution, not just the density
    # near any one region, so it can't be computed inside the contributor
    # itself (contributors are pure functions with no DB access).
    fringe_density_band: BandFunction = field(default_factory=list)

    def __post_init__(self) -> None:
        # A CompositeHeatmapScorer calls every contributor once per region,
        # and several contributors only care about one POI category or
        # project type (e.g. just train stations). Re-filtering the full
        # list on every single region/contributor call is O(regions x
        # total_pois) instead of O(total_pois) - indexing once here, up
        # front, is what makes a fine-grained heatmap grid affordable.
        self._pois_by_category: Dict[POICategory, List[PointOfInterest]] = defaultdict(list)
        for poi in self.points_of_interest:
            self._pois_by_category[poi.category].append(poi)

        self._projects_by_type: Dict[ProjectType, List[Project]] = defaultdict(list)
        for project in self.projects:
            self._projects_by_type[project.project_type].append(project)

        self._poi_buckets: Dict[Tuple[int, int], List[PointOfInterest]] = defaultdict(list)
        for poi in self.points_of_interest:
            self._poi_buckets[self._bucket_key(poi.latitude, poi.longitude, POI_BUCKET_SIZE_KM)].append(poi)

        self._land_cover_buckets: Dict[Tuple[int, int], List[LandCoverCell]] = defaultdict(list)
        for cell in self.land_cover_cells:
            self._land_cover_buckets[
                self._bucket_key(cell.latitude, cell.longitude, LAND_COVER_BUCKET_SIZE_KM)
            ].append(cell)

    def pois_by_category(self, category: POICategory) -> List[PointOfInterest]:
        return self._pois_by_category.get(category, [])

    def projects_by_type(self, project_type: ProjectType) -> List[Project]:
        return self._projects_by_type.get(project_type, [])

    def pois_near(self, lat: float, lon: float, radius_km: float) -> List[PointOfInterest]:
        """POIs in the bucket neighbourhood covering `radius_km` around
        (lat, lon). A cheap first pass, not an exact radius filter - callers
        still need their own distance check for points near the edge of the
        neighbourhood.
        """
        span = math.ceil(radius_km / POI_BUCKET_SIZE_KM)
        center_i, center_j = self._bucket_key(lat, lon, POI_BUCKET_SIZE_KM)
        results: List[PointOfInterest] = []
        for di in range(-span, span + 1):
            for dj in range(-span, span + 1):
                results.extend(self._poi_buckets.get((center_i + di, center_j + dj), []))
        return results

    def land_cover_near(self, lat: float, lon: float, radius_km: float) -> List[LandCoverCell]:
        """Same bucket-neighbourhood approach as pois_near, for
        FringeContributor's density/edge-distance lookups.
        """
        span = math.ceil(radius_km / LAND_COVER_BUCKET_SIZE_KM)
        center_i, center_j = self._bucket_key(lat, lon, LAND_COVER_BUCKET_SIZE_KM)
        results: List[LandCoverCell] = []
        for di in range(-span, span + 1):
            for dj in range(-span, span + 1):
                results.extend(self._land_cover_buckets.get((center_i + di, center_j + dj), []))
        return results

    @staticmethod
    def _bucket_key(lat: float, lon: float, bucket_size_km: float) -> Tuple[int, int]:
        lon_km_per_degree = KM_PER_LAT_DEGREE * math.cos(math.radians(lat))
        return (
            int(lat * KM_PER_LAT_DEGREE // bucket_size_km),
            int(lon * lon_km_per_degree // bucket_size_km),
        )
