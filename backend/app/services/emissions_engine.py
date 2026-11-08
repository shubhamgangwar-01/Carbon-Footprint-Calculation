"""Conference emissions calculation engine.

Core rule:  emissions (kg CO2e) = activity quantity (in the factor's unit) x emission factor

Design principles (GHG Protocol Corporate & Scope 3 Standards; ISO 14064-1):
* Relevance / completeness - every module is reported as calculated, not reported,
  not applicable or incomplete; missing data is NEVER silently treated as zero.
* Consistency - each factor's system boundary is recorded on every line.
* Transparency - every line stores quantity, unit, factor id/value/source and the formula.
* Accuracy / conservativeness - where a default must be assumed, the conservative
  option is chosen and the line is flagged `default`.
* No double counting - metered electricity suppresses load-based estimates; meal and
  ingredient methods are mutually exclusive per service; vehicle modes are counted per
  vehicle-km (shared by occupants) and public modes per passenger-km.

The engine is pure: it takes a ConferenceInput and a FactorRepository and returns a
CalculationResult. It has no database or network dependencies.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from app.calculations import units
from app.calculations.factor_repository import Factor, FactorNotFound, FactorRepository
from app.calculations.geo import airport, flight_distance_km
from app.schemas.conference import (VEHICLE_MODES, AccommodationEntry, ConferenceInput, TransportEntry,
                                    TransportMode)
from app.schemas.results import (CATEGORIES, CATEGORY_LABELS, CalculationLine, CalculationResult, CategoryResult,
                                 Issue)

ENGINE_VERSION = "1.0.0"
SHORT_HAUL_LIMIT_KM = 3700  # DESNZ methodology 8.8 (max range of a Boeing 737) - crude short/long-haul split

COUNTRY_ALIASES = {
    "uk": "uk", "united kingdom": "uk", "great britain": "uk", "england": "uk", "scotland": "uk", "wales": "uk",
    "usa": "united_states", "us": "united_states", "united states of america": "united_states",
    "uae": "united_arab_emirates", "south korea": "korea", "republic of korea": "korea", "hong kong": "hong_kong_china",
    "russia": "russian_federation", "london": "uk_london",
}
ISO2_HOTEL = {"IN": "india", "GB": "uk", "US": "united_states", "AE": "united_arab_emirates", "SG": "singapore",
              "CN": "china", "JP": "japan", "DE": "germany", "FR": "france", "AU": "australia", "TH": "thailand",
              "MY": "malaysia", "ID": "indonesia", "LK": None}

STATIC_ASSUMPTIONS = [
    "GWP basis: IPCC AR5 100-year GWPs (CH4 = 28, N2O = 265), consistent with DESNZ 2026.",
    "Electricity is reported location-based (headline) and market-based (renewable certificates at zero, remainder at grid average because no Indian residual-mix factor is published).",
    "Flight distances are great-circle distances; DESNZ factors already include an 8% routing uplift, so no further uplift is applied.",
    "Flights not touching the UK use DESNZ short-haul factors up to 3,700 km and DESNZ 'International, to/from non-UK' factors above 3,700 km.",
    "Vehicle modes (car, taxi, motorcycle, auto-rickshaw, EV) are calculated per vehicle-km: vehicles = passengers / occupancy unless the number of vehicles is given; public modes (air, rail, bus) per passenger-km.",
    "India-specific road and rail factors (India GHG Program 2015) are published as CO2 only and are converted to CO2e using the CH4/N2O share of the analogous DESNZ 2026 factor.",
    "India grid factor (CEA v22.0, CO2 only) is converted to CO2e using IPCC 2006 default CH4/N2O factors for coal combustion (+0.45%).",
    "Hotel emissions use the Cornell CHSB 2021 country median per occupied room-night (via DESNZ); no hotel-class differentiation is applied because no published class-specific factors exist.",
    "Food factors are Poore & Nemecek (2018) global means (farm-to-retail). Modelled meals use the ICMR-NIN 'My Plate for the Day' (2024) composition; protein-dish portion (100 g raw) is a modelling assumption.",
    "Waste factors follow the DESNZ / GHG Protocol cut-off method: recycling, composting and combustion carry collection and transport only; no avoided-emission credits are claimed.",
]
STATIC_EXCLUSIONS = [
    "Non-CO2 effects of aviation are included only when the radiative-forcing option is enabled.",
    "Well-to-tank (upstream fuel and electricity supply) emissions and electricity T&D losses.",
    "Emissions from virtual participation (devices, networks and data centres) - no robust, openly published factor was found.",
    "Venue construction, furniture and capital goods (GHG Protocol Scope 3 Category 2).",
    "Consumer-stage cooking energy beyond what is captured in venue electricity/fuel data.",
    "Printing process energy and inks (paper material only is counted).",
    "Biogenic CO2 from waste treatment (reported as zero, consistent with DESNZ).",
]


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


class EmissionsEngine:
    def __init__(self, repo: FactorRepository, pinned: Optional[dict[str, str]] = None):
        self.repo = repo
        self.pinned = pinned or {}

    # ------------------------------------------------------------------ helpers
    def _f(self, key: str) -> Factor:
        f = self.repo.get(key, self.pinned)
        self._used[f.factor_key] = f
        return f

    def _line(self, category: str, activity: str, description: str, qty: float, qty_unit: str, f: Optional[Factor],
              emissions: float, data_type: str, formula: str, notes: Optional[list[str]] = None,
              entry_ref: Optional[str] = None, is_proxy: bool = False, dq_override: Optional[str] = None):
        self._n += 1
        self.lines.append(CalculationLine(
            line_id=f"L{self._n:04d}", category=category, activity=activity, description=description,
            entry_ref=entry_ref, quantity=round(qty, 6), quantity_unit=qty_unit,
            factor_id=f.factor_id if f else None, factor_value=f.value if f else None, factor_unit=f.unit if f else None,
            factor_source=f.source_name if f else "User / supplier supplied", factor_geography=f.geography if f else None,
            emissions_kg=round(emissions, 6), data_type=data_type,
            data_quality=dq_override or (f.data_quality_label if f else "medium"),
            data_quality_score=f.data_quality_score if f else None, formula=formula, notes=notes or [],
            is_proxy=is_proxy))
        self._cat_lines[category] += 1

    def _issue(self, level: str, category: str, msg: str, ref: Optional[str] = None):
        self.issues.append(Issue(level=level, category=category, message=msg, entry_ref=ref))
        if level == "error":
            self._incomplete.add(category)

    def _region(self, entry_region: Optional[str]) -> str:
        return (entry_region or self.inp.basic.country_code or "IN").upper()

    # ------------------------------------------------------------------ public API
    def calculate(self, inp: ConferenceInput) -> CalculationResult:
        self.inp = inp
        self.lines: list[CalculationLine] = []
        self.issues: list[Issue] = []
        self.assumptions: list[str] = list(STATIC_ASSUMPTIONS)
        self._used: dict[str, Factor] = {}
        self._n = 0
        self._cat_lines: dict[str, int] = defaultdict(int)
        self._incomplete: set[str] = set()
        self._not_applicable: set[str] = set()
        self._reported: set[str] = set()
        self._loc_elec = 0.0
        self._mkt_elec = 0.0

        self._transport()
        self._accommodation()
        self._energy()
        self._food()
        self._waste()
        self._materials()
        return self._summarise()

    # ================================================================== TRANSPORT
    def _transport(self):
        inp = self.inp
        if inp.transport_not_applicable:
            self._not_applicable.add("transportation")
            return
        if not inp.transport:
            return
        self._reported.add("transportation")
        for e in inp.transport:
            try:
                self._transport_entry(e)
            except (FactorNotFound, KeyError, ValueError) as ex:
                self._issue("error", "transportation", f"{e.label or e.mode.value}: {ex}", e.id)

    def _transport_entry(self, e: TransportEntry):
        mode_name = e.mode.value.replace("_", " ").title()
        if e.label:
            label = e.label
        elif e.origin or e.destination:
            label = f"{mode_name} {e.origin or '?'}→{e.destination or '?'}"
        else:
            label = f"{mode_name}{' - ' + e.group if e.group else ''} ({e.passengers} pax)"
        legs = 2 if e.trip_type == "return" else 1
        notes: list[str] = []
        data_type = e.data_type

        # ---- fuel-based method (actual fuel) takes precedence over distance
        if e.fuel_litres is not None:
            fuel = (e.fuel_type or "diesel").lower()
            key = {"diesel": "energy.fuel.diesel.litre", "petrol": "energy.fuel.petrol.litre",
                   "lpg": "energy.fuel.lpg.litre"}.get(fuel)
            if not key:
                raise ValueError(f"Fuel-based method supports diesel, petrol or LPG (got '{fuel}')")
            f = self._f(key)
            self._line("transportation", "Transport (fuel-based)", label, e.fuel_litres, "litre", f,
                       e.fuel_litres * f.value, data_type, f"{e.fuel_litres:g} L × {f.value:.5f}",
                       ["Fuel-based method used; distance inputs ignored for this entry."], e.id)
            return

        # ---- distance
        dist = e.distance_km
        if dist is not None:
            dist = units.to_km(dist, e.distance_unit)
        countries: set[str] = set()
        if e.mode == TransportMode.flight:
            a, b = airport(e.origin), airport(e.destination)
            if a and b:
                countries = {a["country"], b["country"]}
                if dist is None:
                    dist, _, _ = flight_distance_km(e.origin, e.destination)
                    notes.append(f"Great-circle distance {a['iata']}–{b['iata']} estimated from airport coordinates (OurAirports).")
                    data_type = "estimated" if data_type == "actual" else data_type
        if dist is None:
            self._issue("error", "transportation",
                        f"{label}: distance is missing - enter a one-way distance or valid IATA airport codes. "
                        "This entry is NOT counted (not treated as zero).", e.id)
            return
        if e.distance_source != "user" and data_type == "actual":
            data_type = "estimated"

        # ---- custom / supplier factor
        if e.custom_factor is not None:
            if e.custom_factor_unit == "passenger.km":
                qty = e.passengers * dist * legs * e.trips
                unit = "passenger.km"
            else:
                veh = e.vehicles or (e.passengers / (e.occupancy or 1))
                qty = veh * dist * legs * e.trips
                unit = "vehicle.km"
            self._line("transportation", e.mode.value.replace("_", " ").title(), label, qty, unit, None,
                       qty * e.custom_factor, data_type, f"{qty:,.1f} {unit} × {e.custom_factor:g} (custom)",
                       notes + [f"Custom factor: {e.custom_factor_source or 'source not stated'}"], e.id, dq_override="medium")
            return

        if e.mode == TransportMode.flight:
            self._flight(e, label, dist, legs, countries, notes, data_type)
        elif e.mode in VEHICLE_MODES:
            self._vehicle(e, label, dist, legs, notes, data_type)
        elif e.mode in (TransportMode.train, TransportMode.bus):
            self._public(e, label, dist, legs, notes, data_type)
        else:
            raise ValueError("Mode 'other' requires a custom factor or fuel data")

    def _flight(self, e, label, dist, legs, countries, notes, data_type):
        rf = "with_rf" if self.inp.settings.include_radiative_forcing else "without_rf"
        touches_uk = e.touches_uk or ("GB" in countries)
        cls = e.flight_class
        if touches_uk and countries == {"GB"}:
            band, cls_used = "domestic_uk", "average"
        elif touches_uk:
            band = "short_haul_uk" if dist <= SHORT_HAUL_LIMIT_KM else "long_haul_uk"
            cls_used = cls
        else:
            band = "short_haul_uk" if dist <= SHORT_HAUL_LIMIT_KM else "international_non_uk"
            cls_used = cls
        if band == "short_haul_uk" and cls_used in ("premium_economy", "first"):
            notes.append(f"DESNZ publishes no short-haul {cls_used.replace('_', ' ')} factor; business class used (conservative).")
            cls_used = "business"
        if band == "domestic_uk" and cls != "average":
            notes.append("DESNZ UK-domestic factor is published for average passenger only.")
        f = self._f(f"transport.flight.{band}.{cls_used}.{rf}")
        pkm = e.passengers * dist * legs * e.trips
        if not touches_uk:
            notes.append("DESNZ UK-route factor applied as international proxy (no India-specific aviation factor is published).")
        self._line("transportation", "Air travel", label, pkm, "passenger.km", f, pkm * f.value, data_type,
                   f"{e.passengers} pax × {dist:,.0f} km × {legs} leg(s) × {e.trips} trip(s) × {f.value:.5f}",
                   notes, e.id, is_proxy=not touches_uk)

    def _car_key(self, region: str, size: str, fuel: str) -> tuple[str, bool, list[str]]:
        notes = []
        size = (size or "sedan").lower()
        fuel = (fuel or "petrol").lower()
        if region == "IN":
            if fuel == "bev":
                s = {"hatchback": "small", "small": "small", "sedan": "medium", "medium": "medium", "suv": "large",
                     "muv": "large", "large": "large"}.get(size, "average")
                return f"transport.car.{s}.bev.IN", False, notes
            if fuel == "cng":
                if size not in ("small", "hatchback"):
                    notes.append("Only a small-car CNG factor is published for India; applied to this vehicle.")
                return "transport.car.small.cng.IN", False, notes
            if fuel == "hybrid":
                return "transport.car.hybrid.petrol.IN", False, notes
            if fuel in ("petrol", "diesel"):
                s = {"small": "hatchback", "hatchback": "hatchback", "sedan": "sedan", "medium": "sedan", "average": "sedan",
                     "suv": "suv", "large": "suv", "muv": "muv" if fuel == "diesel" else "suv"}.get(size, "sedan")
                return f"transport.car.{s}.{fuel}.IN", False, notes
            notes.append(f"No India-specific factor for '{fuel}' cars; DESNZ UK factor used as proxy.")
        s = {"hatchback": "small", "small": "small", "sedan": "medium", "medium": "medium", "suv": "large",
             "muv": "large", "large": "large"}.get(size, "average")
        key = f"transport.car.{s}.{fuel}.uk"
        if not self.repo.has(key):
            key = f"transport.car.average.{fuel}.uk"
        is_proxy = region != "GB"
        if is_proxy and not notes:
            notes.append(f"DESNZ UK car factor used as proxy for region {region}.")
        return key, is_proxy, notes

    def _vehicle(self, e, label, dist, legs, notes, data_type):
        region = self._region(e.region)
        occ = e.occupancy
        if e.vehicles:
            vehicles = e.vehicles
            occ_note = f"{e.vehicles} vehicle(s) as entered"
        else:
            if occ is None:
                occ = 1.0
                notes.append("Occupancy not given - conservatively assumed 1 participant per vehicle.")
                if data_type == "actual":
                    data_type = "default"
            vehicles = e.passengers / occ
            occ_note = f"{e.passengers} pax ÷ {occ:g} per vehicle"
        mode = e.mode
        is_proxy = False
        if mode in (TransportMode.car, TransportMode.electric_vehicle, TransportMode.taxi):
            fuel = "bev" if mode == TransportMode.electric_vehicle else (e.fuel_type or None)
            if fuel is None:
                fuel = "petrol"
                notes.append("Fuel type not given - petrol assumed.")
                data_type = "default" if data_type == "actual" else data_type
            if mode == TransportMode.taxi and region != "IN" and fuel not in ("bev", "phev", "hybrid"):
                key, is_proxy = "transport.taxi.regular.uk.vkm", region != "GB"
                if is_proxy:
                    notes.append(f"DESNZ UK taxi factor used as proxy for region {region}.")
            else:
                key, is_proxy, n2 = self._car_key(region, e.vehicle_type, fuel)
                notes += n2
                if mode == TransportMode.taxi:
                    notes.append("Taxi calculated with the car factor for its size/fuel; empty running between fares is excluded.")
            activity = {"car": "Car", "taxi": "Taxi", "electric_vehicle": "Electric vehicle"}[mode.value]
        elif mode == TransportMode.motorcycle:
            size = (e.vehicle_type or ("small" if region == "IN" else "average")).lower()
            if region == "IN":
                size = size if size in ("scooter", "small", "medium", "large") else "small"
                key = f"transport.motorbike.{size}.IN"
            else:
                size = size if size in ("small", "medium", "large", "average") else "average"
                key, is_proxy = f"transport.motorbike.{size}.uk", region != "GB"
            activity = "Motorcycle"
        else:  # auto-rickshaw
            fuel = (e.fuel_type or "cng").lower()
            fuel = fuel if fuel in ("petrol", "diesel", "cng") else "cng"
            key = f"transport.autorickshaw.{fuel}.IN"
            is_proxy = region != "IN"
            if is_proxy:
                notes.append("Three-wheeler factor is India-specific; used as proxy.")
            activity = "Auto-rickshaw"
        f = self._f(key)
        vkm = vehicles * dist * legs * e.trips
        self._line("transportation", activity, label, vkm, "vehicle.km", f, vkm * f.value, data_type,
                   f"({occ_note}) × {dist:,.1f} km × {legs} leg(s) × {e.trips} trip(s) × {f.value:.5f}",
                   notes, e.id, is_proxy=is_proxy)

    def _public(self, e, label, dist, legs, notes, data_type):
        region = self._region(e.region)
        vt = (e.vehicle_type or "").lower()
        is_proxy = False
        if e.mode == TransportMode.train:
            vt = vt or "national"
            if vt == "international":
                key = "transport.rail.international"
                is_proxy = True
            elif vt in ("metro", "light_rail", "tram"):
                key = "transport.rail.light_rail_tram"
                is_proxy = region != "GB"
                if region == "IN":
                    notes.append("India GHG Program rail factors exclude metro/MRTS; DESNZ UK light-rail factor used as proxy.")
            elif region == "IN":
                key = "transport.rail.suburban.IN" if vt == "suburban" else "transport.rail.national.IN"
            else:
                key = "transport.rail.national.uk"
                is_proxy = region != "GB"
            activity = "Rail"
        else:
            vt = vt or ("city" if region == "IN" else "coach")
            if vt in ("coach", "intercity", "chartered"):
                key = "transport.bus.coach.uk"
                is_proxy = region != "GB"
                if region == "IN":
                    notes.append("No India intercity coach factor is published (India GHG Program bus factor is intracity only); DESNZ coach used as proxy.")
            elif region == "IN":
                key = "transport.bus.city.IN"
            else:
                key = "transport.bus.local_average.uk"
                is_proxy = region != "GB"
            activity = "Bus"
        f = self._f(key)
        pkm = e.passengers * dist * legs * e.trips
        self._line("transportation", activity, label, pkm, "passenger.km", f, pkm * f.value, data_type,
                   f"{e.passengers} pax × {dist:,.1f} km × {legs} leg(s) × {e.trips} trip(s) × {f.value:.5f}",
                   notes, e.id, is_proxy=is_proxy)

    # ================================================================== ACCOMMODATION
    def _hotel_key(self, country: str) -> Optional[str]:
        c = country.strip()
        if len(c) == 2 and c.upper() in ISO2_HOTEL and ISO2_HOTEL[c.upper()]:
            slug = ISO2_HOTEL[c.upper()]
        else:
            slug = COUNTRY_ALIASES.get(c.lower(), _slug(c))
        key = f"accommodation.hotel.{slug}"
        return key if self.repo.has(key) else None

    def _grid_factor(self, cc: Optional[str]) -> Optional[Factor]:
        cc = (cc or self.inp.basic.country_code or "").upper()
        if cc == "IN":
            yr = self.inp.settings.grid_reporting_year
            key = f"electricity.grid.IN.FY{yr}" if yr and self.repo.has(f"electricity.grid.IN.FY{yr}") else "electricity.grid.IN"
            return self._f(key)
        if cc == "GB":
            return self._f("electricity.grid.GB")
        return None

    def _accommodation(self):
        inp = self.inp
        if inp.accommodation_not_applicable:
            self._not_applicable.add("accommodation")
            return
        if not inp.accommodation:
            return
        self._reported.add("accommodation")
        for a in inp.accommodation:
            try:
                self._accommodation_entry(a)
            except (FactorNotFound, ValueError) as ex:
                self._issue("error", "accommodation", f"{a.label or a.hotel_name or 'Accommodation'}: {ex}", a.id)

    def _accommodation_entry(self, a: AccommodationEntry):
        label = a.label or a.hotel_name or f"Accommodation ({a.country})"
        # 1) actual energy data
        if a.electricity_kwh is not None or a.diesel_litres or a.lpg_kg or a.natural_gas_m3:
            if a.electricity_kwh:
                g = self._grid_factor(a.grid_country_code or self.inp.basic.country_code)
                if g is None:
                    raise ValueError("Actual hotel electricity given but no grid factor is available for this country - "
                                     "use a hotel-specific factor instead")
                self._line("accommodation", "Hotel energy (actual)", f"{label} - electricity", a.electricity_kwh, "kWh", g,
                           a.electricity_kwh * g.value, a.data_type, f"{a.electricity_kwh:,.0f} kWh × {g.value:.5f}", entry_ref=a.id)
            for qty, key, unit in [(a.diesel_litres, "energy.fuel.diesel.litre", "litre"), (a.lpg_kg, "energy.fuel.lpg.tonne", "kg"),
                                   (a.natural_gas_m3, "energy.fuel.natural_gas.m3", "m3")]:
                if qty:
                    f = self._f(key)
                    val = f.value / 1000 if key.endswith("tonne") else f.value
                    self._line("accommodation", "Hotel energy (actual)", f"{label} - {f.subcategory}", qty, unit, f, qty * val,
                               a.data_type, f"{qty:,.1f} {unit} × {val:.5f}", entry_ref=a.id)
            return
        # room-nights
        notes = []
        data_type = a.data_type
        if a.rooms:
            rooms = a.rooms
        else:
            gpr = a.guests_per_room
            if gpr is None:
                gpr = 1.0
                notes.append("Rooms not given and guests per room unknown - 1 guest per room assumed (conservative).")
                data_type = "default" if data_type == "actual" else data_type
            rooms = (a.guests or 0) / gpr
        room_nights = rooms * a.nights
        # 2) hotel-specific factor
        if a.hotel_factor_kg_per_room_night is not None:
            self._line("accommodation", "Hotel stay (hotel-specific factor)", label, room_nights, "room.night", None,
                       room_nights * a.hotel_factor_kg_per_room_night, data_type,
                       f"{room_nights:,.1f} room-nights × {a.hotel_factor_kg_per_room_night:g}",
                       notes + [f"Hotel-supplied factor: {a.hotel_factor_source or 'source not stated'}"], a.id, dq_override="medium")
            return
        # 3) default country factor
        key = self._hotel_key(a.country)
        if not key:
            raise ValueError(f"No published hotel factor for '{a.country}'. Enter a hotel-specific factor (kg CO2e per room-night).")
        f = self._f(key)
        if a.accommodation_type and a.accommodation_type not in ("hotel", None):
            notes.append(f"Accommodation type '{a.accommodation_type}' - hotel benchmark applied (no type-specific factor published).")
        self._line("accommodation", "Hotel stay", label, room_nights, "room.night", f, room_nights * f.value, data_type,
                   f"{rooms:,.1f} rooms × {a.nights} nights × {f.value:.2f}", notes, a.id)

    # ================================================================== ENERGY
    def _energy(self):
        en = self.inp.energy
        if en is None:
            return
        if en.not_applicable:
            self._not_applicable.add("energy")
            return
        self._reported.add("energy")
        days = self.inp.basic.days or 1
        cc = en.grid_country_code or self.inp.basic.country_code
        grid_kwh: Optional[float] = en.grid_electricity_kwh
        data_type = en.data_type
        estimate_inputs = bool(en.ac_power_kw or en.lighting_power_kw or en.equipment)
        if grid_kwh is not None:
            if estimate_inputs:
                self._issue("info", "energy", "Metered electricity was entered, so AC/lighting/equipment load estimates were "
                                              "ignored to avoid double counting.")
        elif estimate_inputs:
            parts, est = [], 0.0
            if en.ac_power_kw and en.ac_hours_per_day:
                v = en.ac_power_kw * en.ac_hours_per_day * days
                est += v
                parts.append(f"AC {en.ac_power_kw:g} kW × {en.ac_hours_per_day:g} h × {days} d")
            elif en.ac_power_kw or en.ac_hours_per_day:
                self._issue("warning", "energy", "AC estimate needs both electrical power (kW) and hours per day; AC not estimated.")
            if en.lighting_power_kw and en.lighting_hours_per_day:
                v = en.lighting_power_kw * en.lighting_hours_per_day * days
                est += v
                parts.append(f"lighting {en.lighting_power_kw:g} kW × {en.lighting_hours_per_day:g} h × {days} d")
            for q in en.equipment:
                d = q.days or days
                est += q.power_kw * q.quantity * q.hours_per_day * d
                parts.append(f"{q.name} {q.quantity}×{q.power_kw:g} kW × {q.hours_per_day:g} h × {d} d")
            grid_kwh = est
            data_type = "estimated"
            self._issue("info", "energy", "Electricity estimated from rated loads: " + "; ".join(parts) +
                        ". Replace with meter readings for higher accuracy.")
        if grid_kwh is not None and grid_kwh > 0:
            g = self._grid_factor(cc)
            if g is None and en.supplier_factor_kg_per_kwh is None:
                self._issue("error", "energy", f"No grid emission factor available for country '{cc}'. "
                                               "Enter a supplier-specific factor (kg CO2e/kWh).")
            else:
                if g is not None:
                    loc = grid_kwh * g.value
                    self._line("energy", "Grid electricity", f"Venue grid electricity ({cc})", grid_kwh, "kWh", g, loc, data_type,
                               f"{grid_kwh:,.0f} kWh × {g.value:.5f} (location-based)",
                               ["Location-based Scope 2 (GHG Protocol Scope 2 Guidance)."] +
                               ([f"{en.renewable_certified_kwh:,.0f} kWh covered by renewable certificates - reflected in market-based total only."]
                                if en.renewable_certified_kwh else []))
                    self._loc_elec += loc
                else:
                    loc = grid_kwh * en.supplier_factor_kg_per_kwh
                    self._line("energy", "Grid electricity", "Venue grid electricity (supplier factor)", grid_kwh, "kWh", None, loc,
                               data_type, f"{grid_kwh:,.0f} kWh × {en.supplier_factor_kg_per_kwh:g} (supplier)",
                               ["No location-based grid factor available; supplier factor used for both methods."], dq_override="medium")
                    self._loc_elec += loc
                non_ren = grid_kwh - en.renewable_certified_kwh
                mkt_factor = en.supplier_factor_kg_per_kwh if en.supplier_factor_kg_per_kwh is not None else (g.value if g else 0)
                self._mkt_elec += max(non_ren, 0) * mkt_factor
        elif grid_kwh is None:
            self._issue("warning", "energy", "No venue electricity data (metered or estimated) was entered - venue electricity is "
                                             "NOT included in the total.")
            self._incomplete.add("energy")
        if en.onsite_renewable_kwh:
            self._line("energy", "On-site renewable electricity", "Self-generated renewable electricity", en.onsite_renewable_kwh,
                       "kWh", None, 0.0, en.data_type, f"{en.onsite_renewable_kwh:,.0f} kWh × 0",
                       ["Zero operational emissions; embodied emissions of panels excluded."], dq_override="high")
        fuels = [(en.diesel_generator_litres, "energy.fuel.diesel.litre", "litre", "Diesel generator"),
                 (en.petrol_generator_litres, "energy.fuel.petrol.litre", "litre", "Petrol generator"),
                 (en.lpg_litres, "energy.fuel.lpg.litre", "litre", "LPG"),
                 (en.lpg_kg, "energy.fuel.lpg.tonne", "kg", "LPG"),
                 (en.natural_gas_m3, "energy.fuel.natural_gas.m3", "m3", "Natural gas")]
        for qty, key, unit, name in fuels:
            if qty:
                f = self._f(key)
                val = f.value / 1000 if key.endswith("tonne") else f.value
                self._line("energy", "Stationary fuel", name, qty, unit, f, qty * val, en.data_type,
                           f"{qty:,.1f} {unit} × {val:.5f}", ["Scope 1 direct combustion."] +
                           (["Converted from kg CO2e/tonne."] if key.endswith("tonne") else []))

    # ================================================================== FOOD
    def _food(self):
        fd = self.inp.food
        if fd is None:
            return
        if fd.not_applicable:
            self._not_applicable.add("food")
            return
        self._reported.add("food")
        for m in fd.meals:
            if m.count == 0:
                continue
            try:
                f = self._f(f"food.meal.{m.diet}")
            except FactorNotFound:
                self._issue("error", "food", f"No meal model for diet '{m.diet}'", m.id)
                continue
            dt = m.data_type  # activity data (meal counts) as entered; the modelled factor is reflected in data quality
            self._line("food", "Meals (modelled)", f"{m.service.title()} - {f.subcategory}", m.count, "meal", f, m.count * f.value,
                       dt, f"{m.count:,} meals × {f.value:.3f}",
                       ["Per-meal factor is a modelled archetype (NIN plate × Poore & Nemecek); use ingredient quantities for higher accuracy."], m.id)
        for i in fd.ingredients:
            try:
                f = self._f(i.food_key)
            except FactorNotFound:
                self._issue("error", "food", f"Unknown food item '{i.food_key}'", i.id)
                continue
            notes = []
            if i.unit == "litre":
                kg = i.quantity
                notes.append("Litres converted to kg at 1 kg/L (approximation, within ~3% for milk and beverages).")
            else:
                kg = units.to_kg(i.quantity, i.unit)
            self._line("food", "Food (ingredient-based)", f"{f.subcategory} ({i.service})", kg, "kg", f, kg * f.value, i.data_type,
                       f"{kg:,.2f} kg × {f.value:.3f}", notes, i.id)
        bw = fd.bottled_water
        if bw and bw.bottles:
            if bw.bottle_mass_g is None:
                self._issue("error", "food", "Bottled water: empty-bottle PET mass (g) is required (see supplier specification). "
                                             "Bottled water is NOT counted until provided.")
            else:
                pet_kg = bw.bottles * bw.bottle_mass_g / 1000
                f = self._f("materials.plastic.pet.recycled" if bw.recycled_pet else "materials.plastic.pet")
                self._line("food", "Bottled water", "PET bottles (material production)", pet_kg, "kg", f, pet_kg * f.value, bw.data_type,
                           f"{bw.bottles:,} bottles × {bw.bottle_mass_g:g} g = {pet_kg:,.2f} kg × {f.value:.3f}",
                           ["Bottle production only; filling, transport and refrigeration excluded."])
                m3 = bw.bottles * bw.volume_litres / 1000
                w = self._f("water.supply")
                self._line("food", "Bottled water", "Water content (utility supply proxy)", m3, "m3", w, m3 * w.value, bw.data_type,
                           f"{m3:,.3f} m³ × {w.value:.4f}", ["UK water-supply factor used as proxy."], is_proxy=True)

    # ================================================================== WASTE
    ROUTES = [("landfill_kg", "landfill"), ("recycling_kg", "recycling"), ("composting_kg", "composting"),
              ("incineration_kg", "incineration"), ("anaerobic_digestion_kg", "anaerobic_digestion")]

    def _waste(self):
        wd = self.inp.waste
        if wd is None:
            return
        if wd.not_applicable:
            self._not_applicable.add("waste")
            return
        self._reported.add("waste")
        for w in wd.entries:
            routed = 0.0
            for attr, route in self.ROUTES:
                kg = getattr(w, attr)
                if not kg:
                    continue
                routed += kg
                key = f"waste.{w.material}.{route}"
                if route == "recycling" and not self.repo.has(key):
                    key = f"waste.{w.material}.recycling_open_loop"
                if not self.repo.has(key):
                    self._issue("error", "waste", f"{w.material.title()} waste cannot be routed to {route.replace('_', ' ')} "
                                                  "(no published factor / route not applicable).", w.id)
                    continue
                f = self._f(key)
                self._line("waste", "Waste disposal", f"{w.material.title()} → {route.replace('_', ' ')}", kg, "kg", f, kg * f.value,
                           w.data_type, f"{kg:,.1f} kg × {f.value:.5f}",
                           ["UK landfill gas-capture assumptions - likely an UNDER-estimate for Indian landfills/dumpsites."]
                           if route == "landfill" and self.inp.basic.country_code != "GB" else [], w.id,
                           is_proxy=self.inp.basic.country_code != "GB")
            rest = w.generated_kg - routed
            if rest > 1e-9:
                f = self._f(f"waste.{w.material}.landfill")
                self._line("waste", "Waste disposal", f"{w.material.title()} → unassigned (landfill assumed)", rest, "kg", f,
                           rest * f.value, "default", f"{rest:,.1f} kg × {f.value:.5f}",
                           ["Disposal route not specified - landfill assumed (conservative)."], w.id,
                           is_proxy=self.inp.basic.country_code != "GB")

    # ================================================================== MATERIALS
    def _materials(self):
        md = self.inp.materials
        if md is None:
            return
        if md.not_applicable:
            self._not_applicable.add("materials")
            return
        self._reported.add("materials")
        for m in md.entries:
            try:
                f = self._f(m.material_key)
            except FactorNotFound:
                self._issue("error", "materials", f"Unknown material '{m.material_key}' for '{m.item}'", m.id)
                continue
            notes = []
            if m.unit == "items":
                kg = m.quantity * m.unit_mass_g / 1000
                calc = f"{m.quantity:,.0f} items × {m.unit_mass_g:g} g"
            elif m.unit == "pages":
                kg = units.pages_to_paper_kg(m.quantity, m.paper_gsm or 80, m.sheet_size, m.double_sided)
                calc = (f"{m.quantity:,.0f} pages{' (double-sided)' if m.double_sided else ''} × "
                        f"{units.SHEET_AREA_M2[m.sheet_size]:.5f} m² × {m.paper_gsm or 80:g} g/m²")
                notes.append("Paper mass from ISO 216 sheet area × grammage; printing energy/ink excluded.")
            else:
                kg = units.to_kg(m.quantity, m.unit)
                calc = f"{m.quantity:g} {m.unit}"
            em = kg * f.value
            if m.reusable:
                uses = m.expected_uses or self.inp.settings.reusable_item_uses_default
                em /= uses
                notes.append(f"Reusable item: production emissions spread over {uses} expected uses (user assumption).")
                calc += f" ÷ {uses} uses"
            self._line("materials", "Purchased materials", f"{m.item} ({f.subcategory})", kg, "kg", f, em, m.data_type,
                       f"{calc} = {kg:,.2f} kg × {f.value:.3f}", notes, m.id, is_proxy=True)

    # ================================================================== SUMMARY
    def _summarise(self) -> CalculationResult:
        inp = self.inp
        by_cat = defaultdict(float)
        for l in self.lines:
            by_cat[l.category] += l.emissions_kg
        total = sum(by_cat.values())
        cats = []
        for c in CATEGORIES:
            if c in self._not_applicable:
                status = "not_applicable"
            elif c in self._incomplete:
                status = "incomplete"
            elif c in self._reported and self._cat_lines[c]:
                status = "calculated"
            elif c in self._reported:
                status = "incomplete"
            else:
                status = "not_reported"
            cats.append(CategoryResult(category=c, label=CATEGORY_LABELS[c], status=status, emissions_kg=round(by_cat[c], 6),
                                       share_pct=round(100 * by_cat[c] / total, 2) if total else 0.0, line_count=self._cat_lines[c]))
        for c in cats:
            if c.status == "not_reported":
                self._issue("warning", c.category, f"{c.label}: no data entered. This category is reported as 'not reported', "
                                                   "not as zero. Mark it 'not applicable' if it genuinely does not apply.")
        # top activities
        agg = defaultdict(float)
        for l in self.lines:
            agg[(l.category, l.description)] += l.emissions_kg
        top = sorted(agg.items(), key=lambda x: -x[1])[:10]
        top_activities = [{"category": k[0], "activity": k[1], "emissions_kg": round(v, 3),
                           "share_pct": round(100 * v / total, 2) if total else 0} for k, v in top]
        # data type breakdown
        dtb = {t: {"emissions_kg": 0.0, "share_pct": 0.0, "lines": 0} for t in ("actual", "estimated", "default")}
        for l in self.lines:
            dtb[l.data_type]["emissions_kg"] += l.emissions_kg
            dtb[l.data_type]["lines"] += 1
        for t in dtb:
            dtb[t]["emissions_kg"] = round(dtb[t]["emissions_kg"], 3)
            dtb[t]["share_pct"] = round(100 * dtb[t]["emissions_kg"] / total, 2) if total else 0.0
        # data quality (emissions-weighted pedigree score, 1 best - 5 worst)
        w = [(l.emissions_kg, l.data_quality_score) for l in self.lines if l.data_quality_score is not None and l.emissions_kg > 0]
        wsum = sum(e for e, _ in w)
        score = sum(e * s for e, s in w) / wsum if wsum else None
        label = None if score is None else ("high" if score <= 1.75 else "medium" if score <= 2.75 else "low")
        proxy_share = sum(l.emissions_kg for l in self.lines if l.is_proxy) / total * 100 if total else 0
        dq_by_label = defaultdict(float)
        for l in self.lines:
            dq_by_label[l.data_quality] += l.emissions_kg
        uncertainty = ("Low-moderate" if label == "high" and dtb["actual"]["share_pct"] >= 70 else
                       "Moderate" if label in ("high", "medium") and dtb["actual"]["share_pct"] >= 40 else "High")
        n_err = sum(1 for i in self.issues if i.level == "error")
        completeness = {
            "categories_calculated": sum(1 for c in cats if c.status == "calculated"),
            "categories_not_reported": [c.category for c in cats if c.status == "not_reported"],
            "categories_incomplete": [c.category for c in cats if c.status == "incomplete"],
            "categories_not_applicable": [c.category for c in cats if c.status == "not_applicable"],
            "entries_not_counted": n_err,
            "is_complete": all(c.status in ("calculated", "not_applicable") for c in cats) and n_err == 0,
        }
        days = inp.basic.days or 1
        part = inp.basic.total_participants
        offsets = inp.offsets.tonnes_co2e
        assumptions = list(self.assumptions)
        if inp.basic.virtual_attendees:
            assumptions.append(f"{inp.basic.virtual_attendees} virtual attendees are excluded from per-participant metrics and "
                               "their device/network emissions are not quantified.")
        if offsets:
            assumptions.append("Offsets are reported separately and do not reduce gross emissions (GHG Protocol).")
        total_mkt = total - self._loc_elec + self._mkt_elec
        return CalculationResult(
            engine_version=ENGINE_VERSION, factor_set_version=self.repo.factor_set_version,
            calculated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"), conference_name=inp.basic.name,
            total_kg=round(total, 6), total_tonnes=round(total / 1000, 6),
            per_participant_kg=round(total / part, 3) if part else None,
            per_day_kg=round(total / days, 3), per_participant_day_kg=round(total / part / days, 3) if part else None,
            participants=part, days=days,
            location_based_electricity_kg=round(self._loc_elec, 6), market_based_electricity_kg=round(self._mkt_elec, 6),
            total_market_based_kg=round(total_mkt, 6), offsets_tonnes=offsets,
            net_tonnes_after_offsets=round(total / 1000 - offsets, 6),
            by_category=cats, top_activities=top_activities, data_type_breakdown=dtb,
            data_quality={"weighted_score": round(score, 2) if score else None, "label": label,
                          "scale": "1 (best) – 5 (worst), emissions-weighted pedigree score of the factors used",
                          "emissions_by_factor_quality_kg": {k: round(v, 3) for k, v in dq_by_label.items()},
                          "proxy_factor_share_pct": round(proxy_share, 2), "uncertainty_rating": uncertainty},
            completeness=completeness, lines=self.lines, issues=self.issues, assumptions=assumptions,
            exclusions=list(STATIC_EXCLUSIONS),
            factors_used=[{"factor_key": f.factor_key, "factor_id": f.factor_id, "value": f.value, "unit": f.unit,
                           "source": f.source_name, "source_url": f.source_url, "dataset_version": f.dataset_version,
                           "reporting_year": f.reporting_year, "geography": f.geography, "system_boundary": f.system_boundary,
                           "data_quality": f.data_quality_label}
                          for f in sorted(self._used.values(), key=lambda x: x.factor_key)],
        )


def pins_from_result(result: dict) -> dict[str, str]:
    """factor_key -> factor_id map from a stored result, for exact recomputation."""
    return {f["factor_key"]: f["factor_id"] for f in result.get("factors_used", [])}
