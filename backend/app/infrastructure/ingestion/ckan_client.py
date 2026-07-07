from typing import Any, Dict, List

import requests
from requests.exceptions import ChunkedEncodingError


class CkanClient:
    """Thin wrapper around a CKAN portal's standard Action API.

    veri.sakarya.bel.tr (Sakarya municipality open data portal) runs CKAN, so
    this client is generic enough to point at any other CKAN-based Turkish
    municipal open data portal later - only the base_url changes.
    """

    def __init__(self, base_url: str):
        self._base_url = base_url.rstrip("/")

    def search_packages(self, query: str, rows: int = 50) -> List[Dict[str, Any]]:
        response = requests.get(
            f"{self._base_url}/api/3/action/package_search",
            params={"q": query, "rows": rows},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["result"]["results"]

    def get_package(self, package_id: str) -> Dict[str, Any]:
        response = requests.get(
            f"{self._base_url}/api/3/action/package_show",
            params={"id": package_id},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["result"]

    def download_resource(self, url: str) -> bytes:
        # At least one large resource on this portal (the mahalle boundary
        # GeoJSON) reliably has its connection cut a couple hundred bytes
        # short of the declared Content-Length. We tolerate that here and
        # return whatever was received - downstream parsers (e.g.
        # mahalle_geojson_parser) are built to handle a truncated payload.
        response = requests.get(url, stream=True, timeout=120)
        response.raise_for_status()
        chunks = []
        try:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                chunks.append(chunk)
        except ChunkedEncodingError:
            pass
        return b"".join(chunks)
