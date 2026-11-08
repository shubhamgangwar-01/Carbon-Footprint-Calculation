"""What-if scenario engine.

Each preset is a pure transformation of a ConferenceInput. The transformed
input is run through the SAME emissions engine and factor set as the baseline,
so differences are attributable only to the changed arrangement.
"""
from __future__ import annotations

from typing import Any, Callable

from app.calculations.factor_repository import FactorRepository
from app.schemas.conference import ConferenceInput, TransportMode
from app.services.emissions_engine import EmissionsEngine

NON_VEG = {"non_vegetarian_chicken", "non_vegetarian_fish", "non_vegetarian_mutton", "non_vegetarian_beef",
           "non_vegetarian_pork", "non_vegetarian_egg"}
SINGLE_USE_HINTS = ("banner", "lanyard", "badge", "id card", "bag", "kit", "folder", "signage", "standee")


def _copy(inp: ConferenceInput) -> ConferenceInput:
    return ConferenceInput.model_validate(inp.model_dump())


def shared_transport(inp: ConferenceInput, share_pct: float = 100, **_) -> tuple[ConferenceInput, str]:
    """Move car/taxi/motorcycle/auto-rickshaw passengers onto chartered coaches/shuttle buses."""
    out = _copy(inp)
    moved, new = 0, []
    for e in out.transport:
        if e.mode in (TransportMode.car, TransportMode.taxi, TransportMode.motorcycle, TransportMode.autorickshaw) \
                and e.fuel_litres is None and e.custom_factor is None and e.distance_km:
            n = round(e.passengers * share_pct / 100)
            if n <= 0:
                continue
            bus = e.model_copy(update={"id": e.id + "_bus", "mode": TransportMode.bus, "vehicle_type": "coach",
                                       "passengers": n, "vehicles": None, "occupancy": None, "fuel_type": None,
                                       "label": f"Shared shuttle (was {e.mode.value})"})
            new.append(bus)
            moved += n
            if e.vehicles:
                e.vehicles = max(0, round(e.vehicles * (1 - share_pct / 100))) or None
            e.passengers -= n
    out.transport = [e for e in out.transport if e.passengers > 0] + new
    return out, f"{moved} road travellers moved from cars/taxis to shared coaches ({share_pct:.0f}%)."


def public_transport(inp: ConferenceInput, share_pct: float = 100, **_) -> tuple[ConferenceInput, str]:
    """Move car/taxi travellers to rail for trips > 50 km, city bus otherwise."""
    out = _copy(inp)
    moved, new = 0, []
    for e in out.transport:
        if e.mode in (TransportMode.car, TransportMode.taxi) and e.distance_km and e.fuel_litres is None and e.custom_factor is None:
            n = round(e.passengers * share_pct / 100)
            if n <= 0:
                continue
            rail = (e.distance_km or 0) > 50
            new.append(e.model_copy(update={"id": e.id + "_pt", "mode": TransportMode.train if rail else TransportMode.bus,
                                            "vehicle_type": "national" if rail else "city", "passengers": n,
                                            "vehicles": None, "occupancy": None, "fuel_type": None,
                                            "label": f"Public transport (was {e.mode.value})"}))
            moved += n
            e.passengers -= n
            e.vehicles = None
    out.transport = [e for e in out.transport if e.passengers > 0] + new
    return out, f"{moved} car/taxi travellers switched to rail (>50 km) or city bus ({share_pct:.0f}%)."


def rail_for_short_flights(inp: ConferenceInput, max_km: float = 1000, **_) -> tuple[ConferenceInput, str]:
    from app.calculations.geo import airport, flight_distance_km
    out = _copy(inp)
    n = 0
    for e in out.transport:
        if e.mode != TransportMode.flight:
            continue
        d = e.distance_km
        if d is None and airport(e.origin) and airport(e.destination):
            d = flight_distance_km(e.origin, e.destination)[0]
        if d is not None and d <= max_km:
            e.mode, e.vehicle_type, e.distance_km = TransportMode.train, "national", d * 1.0
            e.label = f"Rail instead of flight {e.origin or ''}-{e.destination or ''}"
            n += e.passengers
    return out, (f"{n} flight passengers on routes ≤ {max_km:.0f} km switched to rail "
                 "(rail distance taken equal to flight great-circle distance - real rail routes are usually longer).")


def reduce_travel(inp: ConferenceInput, reduction_pct: float = 25, modes: str = "flight", **_) -> tuple[ConferenceInput, str]:
    out = _copy(inp)
    sel = {m.strip() for m in modes.split(",")}
    for e in out.transport:
        if e.mode.value in sel or "all" in sel:
            e.passengers = max(0, round(e.passengers * (1 - reduction_pct / 100)))
            if e.vehicles:
                e.vehicles = max(1, round(e.vehicles * (1 - reduction_pct / 100)))
    out.transport = [e for e in out.transport if e.passengers > 0 or e.vehicles]
    return out, f"{reduction_pct:.0f}% fewer journeys by {', '.join(sorted(sel))} (e.g. regional speakers, remote talks)."


def virtual_attendance(inp: ConferenceInput, virtual_pct: float = 30, **_) -> tuple[ConferenceInput, str]:
    """A share of in-person attendees join online: their travel, rooms and meals are removed.
    Speakers/staff stay in person; venue energy, waste and materials are kept unchanged (conservative)."""
    out = _copy(inp)
    f = 1 - virtual_pct / 100
    moved = round(out.basic.attendees * virtual_pct / 100)
    for e in out.transport:
        if (e.group or "attendees") == "attendees":
            e.passengers = round(e.passengers * f)
            if e.vehicles:
                e.vehicles = max(1, round(e.vehicles * f))
    out.transport = [e for e in out.transport if e.passengers > 0]
    for a in out.accommodation:
        if a.rooms:
            a.rooms = round(a.rooms * f)
        if a.guests:
            a.guests = round(a.guests * f)
        for k in ("electricity_kwh", "diesel_litres", "lpg_kg", "natural_gas_m3"):
            v = getattr(a, k)
            if v:
                setattr(a, k, v * f)
    if out.food:
        for m in out.food.meals:
            m.count = round(m.count * f)
        for i in out.food.ingredients:
            i.quantity *= f
        if out.food.bottled_water:
            out.food.bottled_water.bottles = round(out.food.bottled_water.bottles * f)
    out.basic.attendees -= moved
    out.basic.virtual_attendees += moved
    out.basic.format = "hybrid"
    return out, (f"{moved} attendees ({virtual_pct:.0f}%) participate online. Travel, accommodation and catering scale down "
                 "for attendee groups; venue energy, waste and materials unchanged; virtual-participation emissions not quantified.")


def vegetarian_meals(inp: ConferenceInput, share_pct: float = 100, target: str = "vegetarian", **_) -> tuple[ConferenceInput, str]:
    out = _copy(inp)
    if not out.food:
        return out, "No meal data - scenario not applicable."
    moved, extra = 0, []
    for m in out.food.meals:
        if m.diet in NON_VEG and m.count:
            n = round(m.count * share_pct / 100)
            m.count -= n
            moved += n
            extra.append(m.model_copy(update={"id": m.id + "_v", "diet": target, "count": n}))
    out.food.meals = [m for m in out.food.meals if m.count > 0] + extra
    return out, f"{moved} non-vegetarian meals ({share_pct:.0f}%) replaced with {target} meals."


def renewable_electricity(inp: ConferenceInput, share_pct: float = 100, mode: str = "certificates", **_) -> tuple[ConferenceInput, str]:
    out = _copy(inp)
    en = out.energy
    if not en or not en.grid_electricity_kwh:
        return out, "No metered grid electricity - scenario not applicable."
    kwh = en.grid_electricity_kwh * share_pct / 100
    if mode == "onsite":
        en.grid_electricity_kwh -= kwh
        en.onsite_renewable_kwh += kwh
        en.renewable_certified_kwh = min(en.renewable_certified_kwh, en.grid_electricity_kwh)
        return out, f"{kwh:,.0f} kWh ({share_pct:.0f}%) supplied by on-site solar instead of the grid (location- and market-based)."
    en.renewable_certified_kwh = min(en.grid_electricity_kwh, en.renewable_certified_kwh + kwh)
    return out, (f"{kwh:,.0f} kWh ({share_pct:.0f}%) covered by renewable energy certificates / green tariff. This lowers the "
                 "MARKET-based total only; the location-based (headline) total is unchanged by design.")


def remove_generator(inp: ConferenceInput, **_) -> tuple[ConferenceInput, str]:
    out = _copy(inp)
    if not out.energy or not out.energy.diesel_generator_litres:
        return out, "No diesel generator use - scenario not applicable."
    from app.calculations.units import to_kwh  # noqa: F401
    litres = out.energy.diesel_generator_litres
    out.energy.diesel_generator_litres = 0
    return out, (f"Diesel generator use ({litres:,.0f} L) eliminated through a reliable grid connection. The replacement grid "
                 "electricity is NOT added (generator kWh output unknown) - result is an upper bound of savings.")


def reusable_materials(inp: ConferenceInput, uses: int = 5, **_) -> tuple[ConferenceInput, str]:
    out = _copy(inp)
    if not out.materials:
        return out, "No materials data - scenario not applicable."
    n = 0
    for m in out.materials.entries:
        if not m.reusable and any(h in m.item.lower() for h in SINGLE_USE_HINTS):
            m.reusable, m.expected_uses = True, uses
            n += 1
    return out, f"{n} single-use items (banners, lanyards, badges, bags, kits) made reusable over {uses} events."


def digital_materials(inp: ConferenceInput, reduction_pct: float = 80, **_) -> tuple[ConferenceInput, str]:
    out = _copy(inp)
    if not out.materials:
        return out, "No materials data - scenario not applicable."
    for m in out.materials.entries:
        if m.material_key.startswith("materials.paper"):
            m.quantity *= (1 - reduction_pct / 100)
    return out, f"Printed paper reduced by {reduction_pct:.0f}% via digital programmes/apps (device energy not counted)."


def reduce_food_waste(inp: ConferenceInput, reduction_pct: float = 50, **_) -> tuple[ConferenceInput, str]:
    out = _copy(inp)
    if not out.waste:
        return out, "No waste data - scenario not applicable."
    for w in out.waste.entries:
        if w.material == "food":
            f = 1 - reduction_pct / 100
            for k in ("generated_kg", "landfill_kg", "recycling_kg", "composting_kg", "incineration_kg", "anaerobic_digestion_kg"):
                setattr(w, k, getattr(w, k) * f)
    return out, (f"Food waste reduced by {reduction_pct:.0f}% through better catering planning. Only disposal emissions are "
                 "modelled; avoided food production would add further savings.")


def compost_food_waste(inp: ConferenceInput, **_) -> tuple[ConferenceInput, str]:
    out = _copy(inp)
    if not out.waste:
        return out, "No waste data - scenario not applicable."
    for w in out.waste.entries:
        if w.material == "food":
            w.composting_kg = w.generated_kg
            w.landfill_kg = w.incineration_kg = w.recycling_kg = w.anaerobic_digestion_kg = 0
    return out, "All food waste segregated and composted instead of landfilled."


PRESETS: dict[str, dict[str, Any]] = {
    "shared_transport": {"fn": shared_transport, "title": "Shared shuttle buses instead of cars/taxis", "category": "transportation",
                         "params": {"share_pct": 100}},
    "public_transport": {"fn": public_transport, "title": "Public transport instead of cars/taxis", "category": "transportation",
                         "params": {"share_pct": 100}},
    "rail_for_short_flights": {"fn": rail_for_short_flights, "title": "Rail instead of short flights", "category": "transportation",
                               "params": {"max_km": 1000}},
    "reduce_travel": {"fn": reduce_travel, "title": "Reduced long-distance travel (regional / remote speakers)",
                      "category": "transportation", "params": {"reduction_pct": 25, "modes": "flight"}},
    "virtual_attendance": {"fn": virtual_attendance, "title": "Hybrid format: share of attendees online", "category": "transportation",
                           "params": {"virtual_pct": 30}},
    "vegetarian_meals": {"fn": vegetarian_meals, "title": "Vegetarian instead of non-vegetarian meals", "category": "food",
                         "params": {"share_pct": 100, "target": "vegetarian"}},
    "renewable_electricity": {"fn": renewable_electricity, "title": "Renewable electricity", "category": "energy",
                              "params": {"share_pct": 100, "mode": "certificates"}},
    "remove_generator": {"fn": remove_generator, "title": "Eliminate diesel generator use", "category": "energy", "params": {}},
    "reusable_materials": {"fn": reusable_materials, "title": "Reusable banners, lanyards and kits", "category": "materials",
                           "params": {"uses": 5}},
    "digital_materials": {"fn": digital_materials, "title": "Digital instead of printed materials", "category": "materials",
                          "params": {"reduction_pct": 80}},
    "reduce_food_waste": {"fn": reduce_food_waste, "title": "Reduced food waste", "category": "waste", "params": {"reduction_pct": 50}},
    "compost_food_waste": {"fn": compost_food_waste, "title": "Compost food waste", "category": "waste", "params": {}},
}


def run_scenario(base: ConferenceInput, preset: str, params: dict | None, repo: FactorRepository,
                 baseline_result=None) -> dict:
    if preset not in PRESETS:
        raise KeyError(f"Unknown scenario '{preset}'")
    p = {**PRESETS[preset]["params"], **(params or {})}
    fn: Callable = PRESETS[preset]["fn"]
    scen_inp, description = fn(base, **p)
    return compare(base, scen_inp, repo, title=PRESETS[preset]["title"], description=description, preset=preset, params=p,
                   baseline_result=baseline_result)


def compare(base: ConferenceInput, scenario: ConferenceInput, repo: FactorRepository, title: str = "Custom scenario",
            description: str = "", preset: str = "custom", params: dict | None = None, baseline_result=None) -> dict:
    b = baseline_result or EmissionsEngine(repo).calculate(base)
    s = EmissionsEngine(repo).calculate(scenario)
    diff = b.total_kg - s.total_kg
    mdiff = b.total_market_based_kg - s.total_market_based_kg
    return {
        "preset": preset, "title": title, "description": description, "params": params or {},
        "baseline_kg": b.total_kg, "scenario_kg": s.total_kg, "reduction_kg": round(diff, 3),
        "reduction_pct": round(100 * diff / b.total_kg, 2) if b.total_kg else 0.0,
        "baseline_market_kg": b.total_market_based_kg, "scenario_market_kg": s.total_market_based_kg,
        "market_reduction_kg": round(mdiff, 3),
        "market_reduction_pct": round(100 * mdiff / b.total_market_based_kg, 2) if b.total_market_based_kg else 0.0,
        "baseline_by_category": {c.category: c.emissions_kg for c in b.by_category},
        "scenario_by_category": {c.category: c.emissions_kg for c in s.by_category},
        "scenario_per_participant_kg": s.per_participant_kg,
        "factor_set_version": s.factor_set_version,
        "applicable": diff != 0 or mdiff != 0,
    }


def run_all(base: ConferenceInput, repo: FactorRepository) -> list[dict]:
    b = EmissionsEngine(repo).calculate(base)
    out = []
    for k in PRESETS:
        try:
            r = run_scenario(base, k, None, repo, baseline_result=b)
        except Exception as ex:  # a scenario must never break the dashboard
            r = {"preset": k, "title": PRESETS[k]["title"], "error": str(ex), "applicable": False}
        out.append(r)
    return out
