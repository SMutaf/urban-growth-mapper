from dataclasses import dataclass
from io import BytesIO
from typing import Iterator

import ijson
from pyproj import Transformer
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shapely_transform

# The source file (Sakarya municipality open data portal) is encoded in a
# legacy Turkish single-byte codepage, not UTF-8, despite being served as
# .geojson. It's also in a projected CRS (EPSG:5254, meters) rather than the
# WGS84 lat/lon (EPSG:4326) the rest of this app stores everything in.
SOURCE_TEXT_ENCODING = "iso-8859-9"
SOURCE_CRS = "EPSG:5254"
TARGET_CRS = "EPSG:4326"

_TURKISH_FOLD = str.maketrans("İIıŞşĞğÜüÖöÇç", "IIISSGGUUOOCC")


def _repair_double_encoded_utf8(text: str) -> str:
    """Fixes a specific, confirmed corruption pattern in the source file:
    some property values were originally correct UTF-8 bytes, but got
    decoded as if they were single-byte Latin-5 (the encoding that *is*
    correct for most of the rest of the file), turning e.g. "ü" (UTF-8 bytes
    C3 BC) into the two separate mojibake characters "Ã¼". Re-encoding as
    Latin-5 and decoding as UTF-8 reverses exactly that mistake. Values that
    were never double-encoded (plain ASCII, or genuinely single-byte
    Latin-5 text) round-trip through this unchanged or raise UnicodeError,
    in which case we keep the original.
    """
    try:
        return text.encode(SOURCE_TEXT_ENCODING).decode("utf-8")
    except UnicodeError:
        return text


def normalize_district_name(name: str) -> str:
    """ASCII-folds a Turkish district name for robust matching.

    Applies the double-encoding repair above first, then folds recognizable
    Turkish letters to ASCII and drops any still-leftover non-ASCII debris -
    a last-resort safety net for whatever corruption the repair doesn't
    catch, trading a little matching precision for robustness.
    """
    repaired = _repair_double_encoded_utf8(name)
    folded = repaired.translate(_TURKISH_FOLD)
    ascii_only = "".join(ch for ch in folded if ch.isascii() and ch.isalnum())
    return ascii_only.upper()


@dataclass
class MahalleBoundary:
    name: str
    district_name: str
    district_name_normalized: str
    geometry: BaseGeometry  # already reprojected to EPSG:4326


def parse_mahalle_boundaries(raw_bytes: bytes) -> Iterator[MahalleBoundary]:
    """Streams mahalle (neighborhood) boundary features out of the raw file
    bytes, tolerating a truncated/incomplete download (the source server
    reliably cuts the response short by a couple hundred bytes) by yielding
    every feature that parsed successfully before the cutoff instead of
    failing the whole ingestion.
    """
    text = raw_bytes.decode(SOURCE_TEXT_ENCODING, errors="replace")
    utf8_stream = BytesIO(text.encode("utf-8"))

    transformer = Transformer.from_crs(SOURCE_CRS, TARGET_CRS, always_xy=True)

    def reproject(x, y, z=None):
        return transformer.transform(x, y)

    try:
        for feature in ijson.items(utf8_stream, "features.item"):
            properties = feature.get("properties", {})
            district_name = properties.get("ilce")
            mahalle_name = properties.get("ad")
            geometry_dict = feature.get("geometry")
            if not district_name or not geometry_dict:
                continue

            try:
                geometry = shape(geometry_dict)
                geometry_wgs84 = shapely_transform(reproject, geometry)
            except (ValueError, TypeError):
                # The truncation point varies between downloads and can land
                # mid-coordinate-ring, producing a feature that's technically
                # complete JSON (so ijson doesn't raise) but has a malformed
                # geometry. Skip just this one feature rather than losing
                # everything parsed so far.
                continue

            repaired_district_name = _repair_double_encoded_utf8(district_name)

            yield MahalleBoundary(
                name=_repair_double_encoded_utf8(mahalle_name or ""),
                district_name=repaired_district_name,
                district_name_normalized=normalize_district_name(district_name),
                geometry=geometry_wgs84,
            )
    except ijson.IncompleteJSONError:
        # Expected: the source stream is truncated near (but not at) EOF.
        # Every feature yielded above this point is complete and usable.
        return
