from app.domain.grid.grid_generator import BoundingBox, GridGenerator


def test_generate_produces_cells_within_bbox():
    bbox = BoundingBox(min_lat=40.0, max_lat=40.1, min_lon=30.0, max_lon=30.1)

    regions = GridGenerator().generate(bbox, cell_size_km=2.0)

    assert len(regions) > 0
    for region in regions:
        assert bbox.min_lat <= region.center_lat <= bbox.max_lat
        assert bbox.min_lon <= region.center_lon <= bbox.max_lon


def test_smaller_cell_size_produces_more_regions():
    bbox = BoundingBox(min_lat=40.0, max_lat=40.2, min_lon=30.0, max_lon=30.2)
    generator = GridGenerator()

    coarse = generator.generate(bbox, cell_size_km=5.0)
    fine = generator.generate(bbox, cell_size_km=1.0)

    assert len(fine) > len(coarse)


def test_boundary_excludes_cells_outside_the_polygon():
    bbox = BoundingBox(min_lat=40.0, max_lat=40.2, min_lon=30.0, max_lon=30.2)
    # A triangle covering only the bottom-left half of the bbox.
    boundary = [(30.0, 40.0), (30.0, 40.2), (30.2, 40.0)]
    generator = GridGenerator()

    unclipped = generator.generate(bbox, cell_size_km=2.0)
    clipped = generator.generate(bbox, cell_size_km=2.0, boundary=boundary)

    assert 0 < len(clipped) < len(unclipped)
