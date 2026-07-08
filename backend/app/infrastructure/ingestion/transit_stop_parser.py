from dataclasses import dataclass
from typing import Any, Dict, Iterator


@dataclass
class TransitStop:
    stop_id: int
    name: str
    latitude: float
    longitude: float
    is_smart_stop: bool
    stop_type_name: str


def extract_stops(route_and_busstops_response: Dict[str, Any]) -> Iterator[TransitStop]:
    """Extracts every bus stop referenced by any route of a single line's
    /route-and-busstops response. The same physical stop is shared by
    multiple lines - callers should dedupe by stop_id across lines.
    """
    for route in route_and_busstops_response.get("routes", []):
        for stop in route.get("busStops", []):
            coordinates = stop.get("busStopGeometry", {}).get("coordinates")
            if not coordinates:
                continue
            longitude, latitude = coordinates[0], coordinates[1]
            yield TransitStop(
                stop_id=stop["id"],
                name=stop.get("name") or f"Durak #{stop.get('busStopNumber', stop['id'])}",
                latitude=latitude,
                longitude=longitude,
                is_smart_stop=bool(stop.get("isSmartStop")),
                stop_type_name=stop.get("busStopTypeName") or "",
            )
