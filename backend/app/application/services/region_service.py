from typing import List

from app.domain.entities.region import Region
from app.domain.grid.grid_generator import BoundingBox, GridGenerator
from app.domain.repositories.interfaces import IRegionRepository


class RegionService:
    def __init__(self, region_repo: IRegionRepository, grid_generator: GridGenerator):
        self._region_repo = region_repo
        self._grid_generator = grid_generator

    def list_regions(self, city: str) -> List[Region]:
        return self._region_repo.list_by_city(city)

    def generate_regions(self, city: str, bbox: BoundingBox, cell_size_km: float) -> List[Region]:
        regions = self._grid_generator.generate(bbox, cell_size_km)
        return self._region_repo.bulk_create(city, regions)
