"""Distance estimation.

1. Flights: offline great-circle distance from OurAirports coordinates (always available).
2. Road/rail (optional, ENABLE_ONLINE_GEOCODING=true): geocode with Nominatim and route with
   OSRM. Results are labelled `estimated_route` (OSRM driving distance) or `estimated_geocode`
   (great-circle between geocoded points, used if routing fails). If the services are disabled
   or unreachable the user is asked to enter the distance manually - nothing is guessed.
"""
from __future__ import annotations

from functools import lru_cache

import httpx

from app.calculations.geo import airport, haversine_km
from app.config import get_settings


@lru_cache(maxsize=512)
def geocode(place: str) -> tuple[float, float, str] | None:
    s = get_settings()
    r = httpx.get(f"{s.nominatim_url}/search", params={"q": place, "format": "json", "limit": 1},
                  headers={"User-Agent": s.geocoder_user_agent}, timeout=10)
    r.raise_for_status()
    js = r.json()
    if not js:
        return None
    return float(js[0]["lat"]), float(js[0]["lon"]), js[0].get("display_name", place)


def estimate(origin: str, destination: str, mode: str) -> dict:
    a, b = airport(origin), airport(destination)
    if mode == "flight":
        if a and b:
            return {"distance_km": round(haversine_km(a["lat"], a["lon"], b["lat"], b["lon"]), 1), "source": "estimated_airport",
                    "method": "Great-circle distance between airport coordinates (OurAirports)",
                    "origin": a, "destination": b}
        return {"error": "Enter 3-letter IATA airport codes (e.g. DEL, BLR, LHR) for automatic flight distances."}
    s = get_settings()
    if not s.enable_online_geocoding:
        return {"error": "Automatic road/rail distance is disabled on this server (ENABLE_ONLINE_GEOCODING=false). "
                         "Please enter the one-way distance manually."}
    try:
        g1, g2 = geocode(origin), geocode(destination)
        if not g1 or not g2:
            return {"error": "Location not found - please enter the distance manually."}
        try:
            r = httpx.get(f"{s.osrm_url}/route/v1/driving/{g1[1]},{g1[0]};{g2[1]},{g2[0]}", params={"overview": "false"},
                          headers={"User-Agent": s.geocoder_user_agent}, timeout=15)
            r.raise_for_status()
            km = r.json()["routes"][0]["distance"] / 1000
            return {"distance_km": round(km, 1), "source": "estimated_route",
                    "method": "OSRM driving route between OpenStreetMap/Nominatim geocodes",
                    "origin": {"name": g1[2]}, "destination": {"name": g2[2]},
                    "note": "Road distance; rail routes may differ."}
        except (httpx.HTTPError, KeyError, IndexError):
            km = haversine_km(g1[0], g1[1], g2[0], g2[1])
            return {"distance_km": round(km, 1), "source": "estimated_geocode",
                    "method": "Great-circle distance between geocoded points (routing unavailable) - real travel distance is longer",
                    "origin": {"name": g1[2]}, "destination": {"name": g2[2]}}
    except httpx.HTTPError as ex:
        return {"error": f"Distance service unavailable ({ex.__class__.__name__}) - please enter the distance manually."}
