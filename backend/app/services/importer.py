"""CSV / Excel bulk import of attendee travel records.

Pipeline: read -> normalise headers -> normalise units/values -> validate each row
with the TransportEntry schema -> detect duplicates -> report invalid rows with
row numbers and reasons. Valid rows are returned; nothing is silently dropped.

Expected columns (case/spacing-insensitive; aliases accepted):
  mode, origin, destination, distance, distance_unit, passengers, trip_type,
  trips, vehicle_type, fuel_type, occupancy, flight_class, group, attendee_id, label
"""
from __future__ import annotations

import hashlib
import io
from typing import Any

import pandas as pd
from pydantic import ValidationError

from app.calculations.geo import airport
from app.schemas.conference import TransportEntry

ALIASES = {
    "mode": ["mode", "transport_mode", "travel_mode", "mode_of_transport"],
    "origin": ["origin", "from", "departure", "start", "origin_city", "from_airport"],
    "destination": ["destination", "to", "arrival", "end", "destination_city", "to_airport"],
    "distance_km": ["distance", "distance_km", "km", "one_way_distance", "one_way_distance_km"],
    "distance_unit": ["distance_unit", "unit"],
    "passengers": ["passengers", "travellers", "travelers", "pax", "people", "count"],
    "trip_type": ["trip_type", "journey", "return", "one_way_or_return", "journey_type"],
    "trips": ["trips", "number_of_trips", "journeys"],
    "vehicle_type": ["vehicle_type", "vehicle", "car_type", "bus_type", "train_type"],
    "fuel_type": ["fuel_type", "fuel"],
    "occupancy": ["occupancy", "persons_per_vehicle", "vehicle_occupancy"],
    "vehicles": ["vehicles", "number_of_vehicles"],
    "flight_class": ["flight_class", "class", "cabin", "cabin_class"],
    "group": ["group", "participant_type", "role", "category"],
    "attendee_id": ["attendee_id", "id", "participant_id", "registration_id", "email"],
    "label": ["label", "name", "description", "note"],
    "fuel_litres": ["fuel_litres", "fuel_used_litres", "litres"],
}
MODE_MAP = {
    "flight": "flight", "air": "flight", "airplane": "flight", "aeroplane": "flight", "plane": "flight", "fly": "flight",
    "train": "train", "rail": "train", "metro": "train", "railway": "train",
    "bus": "bus", "coach": "bus", "shuttle": "bus",
    "car": "car", "petrol car": "car", "diesel car": "car", "own car": "car",
    "taxi": "taxi", "cab": "taxi", "uber": "taxi", "ola": "taxi",
    "motorcycle": "motorcycle", "motorbike": "motorcycle", "bike": "motorcycle", "two wheeler": "motorcycle", "scooter": "motorcycle",
    "auto": "autorickshaw", "autorickshaw": "autorickshaw", "auto rickshaw": "autorickshaw", "auto-rickshaw": "autorickshaw", "three wheeler": "autorickshaw",
    "ev": "electric_vehicle", "electric car": "electric_vehicle", "electric vehicle": "electric_vehicle", "electric_vehicle": "electric_vehicle",
    "other": "other",
}
CLASS_MAP = {"economy": "economy", "eco": "economy", "y": "economy", "premium": "premium_economy",
             "premium economy": "premium_economy", "premium_economy": "premium_economy", "w": "premium_economy",
             "business": "business", "j": "business", "c": "business", "first": "first", "f": "first", "average": "average"}


def _norm(s: str) -> str:
    return str(s).strip().lower().replace(" ", "_").replace("-", "_")


def read_table(content: bytes, filename: str) -> pd.DataFrame:
    name = filename.lower()
    if name.endswith((".xlsx", ".xlsm", ".xls")):
        return pd.read_excel(io.BytesIO(content), dtype=str)
    if name.endswith(".csv") or name.endswith(".txt"):
        for enc in ("utf-8-sig", "latin-1"):
            try:
                return pd.read_csv(io.BytesIO(content), dtype=str, encoding=enc)
            except UnicodeDecodeError:
                continue
    raise ValueError("Unsupported file type - upload .csv or .xlsx")


def map_columns(df: pd.DataFrame) -> tuple[dict[str, str], list[str]]:
    cols = {_norm(c): c for c in df.columns}
    mapping, unknown = {}, []
    for field, names in ALIASES.items():
        for n in names:
            if n in cols:
                mapping[field] = cols[n]
                break
    used = set(mapping.values())
    unknown = [c for c in df.columns if c not in used]
    return mapping, unknown


def _val(row, mapping, field):
    c = mapping.get(field)
    if c is None:
        return None
    v = row.get(c)
    if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == "" or str(v).strip().lower() in ("nan", "none"):
        return None
    return str(v).strip()


def import_transport(content: bytes, filename: str, default_trip_type: str = "return") -> dict[str, Any]:
    df = read_table(content, filename)
    if df.empty:
        raise ValueError("The file has no data rows")
    mapping, unknown = map_columns(df)
    if "mode" not in mapping:
        raise ValueError("Required column 'mode' not found. Accepted names: " + ", ".join(ALIASES["mode"]))
    valid: list[dict] = []
    errors: list[dict] = []
    warnings: list[dict] = []
    seen: dict[str, int] = {}
    for idx, row in df.iterrows():
        rn = int(idx) + 2  # spreadsheet row number (header = 1)
        try:
            raw_mode = (_val(row, mapping, "mode") or "").lower()
            mode = MODE_MAP.get(raw_mode)
            if not mode:
                raise ValueError(f"Unknown transport mode '{raw_mode}'")
            d = {"mode": mode, "origin": _val(row, mapping, "origin"), "destination": _val(row, mapping, "destination"),
                 "group": _val(row, mapping, "group"), "label": _val(row, mapping, "label")}
            dist = _val(row, mapping, "distance_km")
            if dist is not None:
                d["distance_km"] = float(dist.replace(",", ""))
                unit = (_val(row, mapping, "distance_unit") or "km").lower()
                d["distance_unit"] = "miles" if unit in ("mi", "mile", "miles") else "km"
            elif mode == "flight":
                if not (airport(d["origin"]) and airport(d["destination"])):
                    raise ValueError("Flight row needs a distance or valid IATA airport codes for origin and destination")
                d["distance_source"] = "estimated_airport"
            elif _val(row, mapping, "fuel_litres") is None:
                raise ValueError("Distance is missing")
            pax = _val(row, mapping, "passengers")
            d["passengers"] = int(float(pax)) if pax else 1
            tt = (_val(row, mapping, "trip_type") or default_trip_type).lower()
            d["trip_type"] = "return" if tt in ("return", "round", "round trip", "roundtrip", "yes", "y", "true", "2") else "one_way"
            for f, conv in (("trips", lambda x: int(float(x))), ("occupancy", float), ("vehicles", lambda x: int(float(x))),
                            ("fuel_litres", float)):
                v = _val(row, mapping, f)
                if v is not None:
                    d[f] = conv(v)
            for f in ("vehicle_type", "fuel_type"):
                v = _val(row, mapping, f)
                if v:
                    d[f] = v.lower().replace(" ", "_")
            fc = _val(row, mapping, "flight_class")
            if fc:
                if fc.lower() not in CLASS_MAP:
                    raise ValueError(f"Unknown flight class '{fc}'")
                d["flight_class"] = CLASS_MAP[fc.lower()]
            entry = TransportEntry.model_validate(d)
            att = _val(row, mapping, "attendee_id") or ""
            sig = hashlib.sha1("|".join(str(x) for x in (att, mode, (d["origin"] or "").lower(), (d["destination"] or "").lower(),
                                                        d.get("distance_km"), d["trip_type"], d["passengers"])).encode()).hexdigest()
            if sig in seen:
                warnings.append({"row": rn, "message": f"Duplicate of row {seen[sig]} - skipped"})
                continue
            seen[sig] = rn
            valid.append(entry.model_dump(mode="json") | {"_row": rn})
        except (ValueError, ValidationError) as ex:
            msg = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in ex.errors()) if isinstance(ex, ValidationError) else str(ex)
            errors.append({"row": rn, "message": msg})
    return {"total_rows": len(df), "valid_rows": len(valid), "invalid_rows": len(errors), "duplicates": len(warnings),
            "column_mapping": mapping, "unrecognised_columns": unknown, "entries": valid, "errors": errors, "warnings": warnings}


TEMPLATE_CSV = """attendee_id,group,mode,origin,destination,distance_km,trip_type,passengers,vehicle_type,fuel_type,occupancy,flight_class
A001,attendees,flight,DEL,BLR,,return,1,,,,economy
A002,speakers,flight,LHR,BLR,,return,1,,,,business
A003,attendees,train,Chennai,Bengaluru,350,return,1,national,,,
A004,attendees,car,Mysuru,Bengaluru,145,return,3,sedan,diesel,3,
A005,attendees,bus,Hosur,Bengaluru,40,return,1,city,,,
A006,attendees,autorickshaw,Hotel,Venue,6,return,2,,cng,2,
"""
