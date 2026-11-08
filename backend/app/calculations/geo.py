"""Distance helpers: offline airport lookup (OurAirports, public domain) and
great-circle distance. Optional online geocoding/routing lives in
app/services/distance.py so the calculator works fully offline."""
from __future__ import annotations

import csv
import math
from functools import lru_cache
from pathlib import Path

AIRPORTS_CSV = Path(__file__).resolve().parents[3] / "data" / "processed" / "transportation" / "airports.csv"
EARTH_RADIUS_KM = 6371.0088  # IUGG mean Earth radius


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


@lru_cache(maxsize=1)
def airports() -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not AIRPORTS_CSV.exists():
        return out
    with AIRPORTS_CSV.open() as f:
        for r in csv.DictReader(f):
            out[r["iata_code"].upper()] = {
                "iata": r["iata_code"].upper(), "name": r["name"], "city": r["municipality"],
                "country": r["iso_country"], "lat": float(r["latitude_deg"]), "lon": float(r["longitude_deg"]),
            }
    return out


def airport(code: str | None) -> dict | None:
    if not code:
        return None
    return airports().get(code.strip().upper()[:3]) if len(code.strip()) >= 3 else None


def flight_distance_km(origin: str, destination: str) -> tuple[float, dict, dict]:
    a, b = airport(origin), airport(destination)
    if not a or not b:
        missing = origin if not a else destination
        raise KeyError(f"Unknown IATA airport code '{missing}'")
    return haversine_km(a["lat"], a["lon"], b["lat"], b["lon"]), a, b


def search_airports(q: str, limit: int = 15) -> list[dict]:
    q = q.strip().lower()
    if not q:
        return []
    res = []
    for ap in airports().values():
        score = 0
        if ap["iata"].lower() == q:
            score = 3
        elif (ap["city"] or "").lower().startswith(q):
            score = 2
        elif q in ap["name"].lower() or q in (ap["city"] or "").lower():
            score = 1
        if score:
            res.append((score, ap))
    res.sort(key=lambda x: (-x[0], x[1]["iata"]))
    return [a for _, a in res[:limit]]
