"""Recommendations generated from the actual calculation results.

A recommendation is only produced when (a) the related category/activity is a
material share of THIS conference's footprint and (b) the quantified scenario
shows a non-zero reduction. Each item carries the evidence that triggered it.
"""
from __future__ import annotations

from collections import defaultdict

from app.schemas.results import CATEGORY_LABELS, CalculationResult

MATERIAL_SHARE = 5.0  # % of total - below this a category is not prioritised


def generate(result: CalculationResult, scenarios: list[dict]) -> list[dict]:
    total = result.total_kg
    if total <= 0:
        return []
    share = {c.category: c.share_pct for c in result.by_category}
    by_activity = defaultdict(float)
    for l in result.lines:
        by_activity[(l.category, l.activity)] += l.emissions_kg
    act_share = {k: 100 * v / total for k, v in by_activity.items()}
    sc = {s["preset"]: s for s in scenarios if s.get("applicable")}
    recs: list[dict] = []

    def add(category, title, actions, evidence, preset_keys, priority_basis):
        # only scenarios that actually reduce emissions (some switches increase them, e.g. coach vs shared CNG taxi)
        quant = [sc[p] for p in preset_keys if p in sc and (sc[p]["reduction_kg"] > 0 or sc[p].get("market_reduction_kg", 0) > 0)]
        best = max(quant, key=lambda s: max(s["reduction_kg"], s.get("market_reduction_kg", 0)), default=None)
        basis = None
        pot_kg = pot_pct = None
        if best:
            if best["reduction_kg"] > 0:
                basis, pot_kg, pot_pct = "location-based (gross)", best["reduction_kg"], best["reduction_pct"]
            else:
                basis, pot_kg, pot_pct = "market-based", best["market_reduction_kg"], best["market_reduction_pct"]
        recs.append({
            "category": category, "category_label": CATEGORY_LABELS.get(category, category), "title": title,
            "actions": actions, "evidence": evidence,
            "potential_reduction_kg": pot_kg,
            "potential_reduction_pct": pot_pct,
            "potential_basis": basis,
            "potential_market_reduction_kg": best.get("market_reduction_kg") if best else None,
            "scenario": best["preset"] if best else None, "scenario_title": best["title"] if best else None,
            "related_scenarios": [{"preset": q["preset"], "title": q["title"], "reduction_kg": q["reduction_kg"],
                                   "reduction_pct": q["reduction_pct"]} for q in quant],
            "priority_basis": priority_basis,
        })

    # ---------------------------------------------------------------- transport
    t = share.get("transportation", 0)
    air = act_share.get(("transportation", "Air travel"), 0)
    road = sum(v for (c, a), v in act_share.items() if c == "transportation" and a in ("Car", "Taxi", "Motorcycle", "Auto-rickshaw"))
    if air >= MATERIAL_SHARE:
        add("transportation", "Cut long-distance air travel",
            ["Invite regional speakers or offer remote keynote slots for distant speakers.",
             "Offer a hybrid/virtual registration tier for international delegates.",
             "Encourage rail for journeys under ~1,000 km and economy class for necessary flights.",
             "Choose a venue that minimises total delegate travel distance."],
            f"Air travel is {air:.1f}% of this conference's footprint.",
            ["reduce_travel", "virtual_attendance", "rail_for_short_flights"], air)
    if road >= MATERIAL_SHARE:
        add("transportation", "Shift local road travel to shared and public transport",
            ["Run shuttle buses between hotels, transit hubs and the venue.",
             "Publish public-transport/metro directions and offer transit passes with registration.",
             "Promote car-pooling and EV taxis where available."],
            f"Cars, taxis and two/three-wheelers are {road:.1f}% of the footprint.",
            ["shared_transport", "public_transport"], road)
    elif t >= MATERIAL_SHARE and air < MATERIAL_SHARE:
        add("transportation", "Optimise delegate travel", ["Promote public transport and shared shuttles."],
            f"Transportation is {t:.1f}% of the footprint.", ["shared_transport", "public_transport"], t)

    # ---------------------------------------------------------------- accommodation
    a = share.get("accommodation", 0)
    if a >= MATERIAL_SHARE:
        add("accommodation", "Choose lower-carbon accommodation",
            ["Block rooms in hotels within walking distance of the venue to also cut local transport.",
             "Prefer hotels that report energy data or hold recognised green certifications; request their kg CO2e per room-night.",
             "Encourage room sharing and avoid unnecessary extra nights through programme scheduling."],
            f"Accommodation is {a:.1f}% of the footprint (default CHSB country benchmark used unless hotel data supplied). "
            "Savings depend on the chosen hotel's own data, so no generic reduction is estimated.",
            [], a)

    # ---------------------------------------------------------------- energy
    e = share.get("energy", 0)
    gen = act_share.get(("energy", "Stationary fuel"), 0)
    grid = act_share.get(("energy", "Grid electricity"), 0)
    if grid >= MATERIAL_SHARE:
        add("energy", "Reduce and decarbonise venue electricity",
            ["Procure renewable electricity (green tariff / I-RECs) - reported in the market-based total.",
             "Choose venues with on-site solar or certified energy management (e.g. ISO 50001).",
             "Set AC to 24–26 °C (BEE guidance), switch to LED lighting and power down equipment between sessions."],
            f"Grid electricity is {grid:.1f}% of the footprint (location-based).", ["renewable_electricity"], grid)
    if gen >= 1.0:
        add("energy", "Avoid diesel generators",
            ["Secure a reliable grid connection; use generators only as emergency backup.",
             "Right-size backup capacity or use battery storage for short outages."],
            f"Stationary fuel (generators) is {gen:.1f}% of the footprint.", ["remove_generator"], gen)

    # ---------------------------------------------------------------- food
    f = share.get("food", 0)
    meals = [l for l in result.lines if l.category == "food" and l.activity.startswith("Meals")]
    nonveg = sum(l.emissions_kg for l in meals if "Non Vegetarian" in l.description)
    if f >= MATERIAL_SHARE or (meals and nonveg / total * 100 >= 2):
        add("food", "Lower-emission menus and better catering planning",
            ["Make vegetarian the default menu option (meat/fish on request).",
             "Avoid beef and mutton; prefer pulses, seasonal vegetables and millets.",
             "Base catering quantities on confirmed registrations and day-wise attendance.",
             "Replace bottled water with refill stations."],
            f"Food & beverages are {f:.1f}% of the footprint; non-vegetarian meals contribute {100 * nonveg / total:.1f}%.",
            ["vegetarian_meals"], f)

    # ---------------------------------------------------------------- waste
    w = share.get("waste", 0)
    lf = sum(l.emissions_kg for l in result.lines if l.category == "waste" and "landfill" in l.description.lower())
    if w >= 1.0 or (lf and lf / total * 100 >= 0.5):
        add("waste", "Divert waste from landfill",
            ["Segregate waste at source (wet/dry/recyclables) with clearly labelled bins (SWM Rules 2016).",
             "Compost or bio-methanate food waste; donate surplus food through registered food-recovery partners.",
             "Track waste by weight with the venue's waste contractor."],
            f"Waste is {w:.1f}% of the footprint; landfilled waste contributes {100 * lf / total:.1f}%.",
            ["compost_food_waste", "reduce_food_waste"], w)

    # ---------------------------------------------------------------- materials
    m = share.get("materials", 0)
    if m >= 1.0:
        add("materials", "Go digital and reusable",
            ["Use a conference app/website instead of printed programmes.",
             "Use undated, reusable banners and fabric signage; collect lanyards and badge holders for reuse.",
             "Avoid giveaway kits or choose recycled-content, locally made items."],
            f"Materials & procurement are {m:.1f}% of the footprint.", ["digital_materials", "reusable_materials"], m)

    # ---------------------------------------------------------------- data quality
    dflt = result.data_type_breakdown.get("default", {}).get("share_pct", 0) + \
        result.data_type_breakdown.get("estimated", {}).get("share_pct", 0)
    if dflt >= 30 or result.completeness.get("categories_not_reported"):
        missing = ", ".join(CATEGORY_LABELS[c] for c in result.completeness.get("categories_not_reported", []))
        recs.append({
            "category": "data_quality", "category_label": "Data quality", "title": "Improve the data behind this footprint",
            "actions": ["Collect actual travel data (origin, mode, class) through the registration form.",
                        "Obtain metered electricity, generator fuel logs and hotel energy data.",
                        "Weigh waste by stream with the venue/waste contractor."] +
                       ([f"Enter data for categories not yet reported: {missing}."] if missing else []),
            "evidence": f"{dflt:.1f}% of emissions rely on estimated or default activity data." +
                        (f" Not reported: {missing}." if missing else ""),
            "potential_reduction_kg": None, "potential_reduction_pct": None, "scenario": None, "related_scenarios": [],
            "priority_basis": 0,
        })
    recs.sort(key=lambda r: (r["category"] == "data_quality", -(r["potential_reduction_kg"] or 0), -r["priority_basis"]))
    for i, r in enumerate(recs, 1):
        r["rank"] = i
    return recs
