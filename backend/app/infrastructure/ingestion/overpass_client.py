from typing import Any, Dict, List

import requests

# The public instance rejects requests without a descriptive User-Agent
# (returns 406/429), and can be slow/overloaded for broad "name" area
# lookups - keep queries scoped to a known area id (looked up once via
# Nominatim) rather than resolving the area by name on every run.
DEFAULT_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "urban-growth-mapper/0.1 (Sakarya MVP; contact: mutafmutaf76@gmail.com)"


class OverpassClient:
    def __init__(self, base_url: str = DEFAULT_OVERPASS_URL):
        self._base_url = base_url

    def query(self, overpass_ql: str, timeout: int = 150) -> List[Dict[str, Any]]:
        response = requests.post(
            self._base_url,
            data={"data": overpass_ql},
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()["elements"]
