from app.domain.grid.grid_generator import BoundingBox

# Placeholder bounding boxes for the MVP pilot city. Coordinates approximate the
# Adapazari/Sakarya urban area and should be verified/refined with real GIS data
# before anything derived from them is treated as authoritative.
CITY_BOUNDING_BOXES = {
    "sakarya": BoundingBox(min_lat=40.65, max_lat=40.85, min_lon=30.25, max_lon=30.55),
}
