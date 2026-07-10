import re
import zipfile
from dataclasses import dataclass
from io import BytesIO
from typing import Dict, List

# Sakarya municipality's KMZ exports all follow the same pattern: a
# Placemark's real attributes live in an HTML table embedded in its
# <description> CDATA (key/value table rows), not in <name>, which is
# usually empty. This parser is generic to that pattern - reusable across
# their different KMZ datasets (hospitals, Kart54 points, etc.), as long as
# the placemark geometry is a single Point.
_TABLE_ROW_PATTERN = re.compile(
    r"<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*</tr>", re.DOTALL
)
_TAG_STRIP_PATTERN = re.compile(r"<[^>]+>")
_COORDINATES_PATTERN = re.compile(r"<coordinates>\s*([\-\d.]+)\s*,\s*([\-\d.]+)")


@dataclass
class KmlPlacemark:
    properties: Dict[str, str]
    latitude: float
    longitude: float


def _strip_tags(html: str) -> str:
    return _TAG_STRIP_PATTERN.sub("", html).strip()


def parse_kmz_point_placemarks(kmz_bytes: bytes) -> List[KmlPlacemark]:
    with zipfile.ZipFile(BytesIO(kmz_bytes)) as archive:
        kml_name = next(name for name in archive.namelist() if name.lower().endswith(".kml"))
        kml_text = archive.read(kml_name).decode("utf-8", errors="replace")

    placemarks = []
    for match in re.finditer(r"<Placemark.*?</Placemark>", kml_text, re.DOTALL):
        placemark_text = match.group(0)

        coordinates = _COORDINATES_PATTERN.search(placemark_text)
        if not coordinates:
            continue
        longitude, latitude = float(coordinates.group(1)), float(coordinates.group(2))

        properties = {}
        for key_html, value_html in _TABLE_ROW_PATTERN.findall(placemark_text):
            key = _strip_tags(key_html)
            if key:
                properties[key] = _strip_tags(value_html)

        placemarks.append(KmlPlacemark(properties=properties, latitude=latitude, longitude=longitude))
    return placemarks
