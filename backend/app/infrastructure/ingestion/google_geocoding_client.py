from typing import Optional, Tuple

import requests

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


class GoogleGeocodingClient:
    """One-time address -> coordinate lookup, per the usage the user
    explicitly signed off on: 686 school addresses geocoded once during
    ingestion and stored in our own database, not re-queried per end user.
    """

    def __init__(self, api_key: str):
        self._api_key = api_key

    def geocode(self, address: str) -> Optional[Tuple[float, float, str]]:
        """Returns (lat, lon, location_type) or None if no result."""
        response = requests.get(
            GEOCODE_URL,
            params={"address": address, "key": self._api_key, "region": "tr"},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("status") != "OK" or not data.get("results"):
            return None
        result = data["results"][0]
        location = result["geometry"]["location"]
        location_type = result["geometry"].get("location_type", "")
        return location["lat"], location["lng"], location_type
