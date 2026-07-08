from typing import Any, Dict, Optional

import requests

# This API backs Sakarya Buyuksehir Belediyesi's own live bus tracking site
# (sakus.sakarya.bel.tr/harita) and is not formally documented, but is
# publicly reachable with no authentication - only an Origin/Referer header
# matching their own frontend (a basic anti-scraping check, not access
# control). We call it exactly as that public page already does.
BASE_URL = "https://sbbpublicapi.sakarya.bel.tr/api/v1/Ulasim"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Origin": "https://sakus.sakarya.bel.tr",
    "Referer": "https://sakus.sakarya.bel.tr/harita",
}


class SakaryaTransitClient:
    def get_route_and_busstops(self, line_id: int) -> Optional[Dict[str, Any]]:
        response = requests.get(
            f"{BASE_URL}/route-and-busstops/{line_id}", headers=HEADERS, timeout=20
        )
        # An invalid/unassigned line_id returns 204 No Content (not 404).
        if response.status_code in (204, 404) or not response.content:
            return None
        response.raise_for_status()
        return response.json()
