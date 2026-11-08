#!/usr/bin/env python3
"""Turn the raw, unmodified source files in data/raw/ into the application's
standardised emission-factor database.

Outputs
-------
data/processed/<category>/*.csv           cleaned per-category extracts
data/processed/emission_factors.json      the central factor database (all versions)
data/processed/emission_factors.csv       same, flat
data/processed/meal_models.json           documented meal archetypes (food module)
data/processed/airports.csv               IATA airports with coordinates
data/processed/electricity/india_generation_mix_FY2025-26.csv
data/metadata/dataset_versions.json
data/metadata/data_quality.json

Every factor is read from a downloaded original. Where a factor is *derived*
(unit conversion, CO2->CO2e adjustment, meal model) the derivation formula and
inputs are stored on the record so the number can be reproduced by hand.
"""
from __future__ import annotations

import csv
import json
import re
from datetime import date
from pathlib import Path

import pandas as pd
import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
META = ROOT / "data" / "metadata"
TODAY = date.today().isoformat()

registry = {s["source_id"]: s for s in json.loads((META / "source_registry.json").read_text())["sources"]}

# AR5 100-year GWPs (IPCC AR5 WG1 Table 8.7, without climate-carbon feedback) - same basis as DESNZ 2026
GWP_AR5 = {"CO2": 1, "CH4": 28, "N2O": 265}
# IPCC 2006 Guidelines Vol.2 Ch.2 Table 2.2 - default emission factors for stationary combustion in
# the energy industries, Other Bituminous Coal (kg/TJ on a net calorific basis)
IPCC_COAL_EF = {"CO2": 94600, "CH4": 1, "N2O": 1.5}

FACTORS: list[dict] = []
QUALITY: dict[str, dict] = {}


def src(sid: str) -> dict:
    s = registry[sid]
    if s["status"] != "downloaded":
        raise SystemExit(f"Source {sid} was not downloaded - cannot build factors from it")
    return s


def quality(score_geo: int, score_time: int, score_tech: int, score_rel: int, note: str) -> dict:
    """Pedigree-style data-quality indicator (1 = best, 5 = worst) after Weidema & Wesnaes (1996),
    as used by ecoinvent and recommended in GHG Protocol Scope 3 Standard ch.7 (data-quality
    indicators: technological, temporal, geographical representativeness, completeness, reliability)."""
    avg = (score_geo + score_time + score_tech + score_rel) / 4
    label = "high" if avg <= 1.75 else "medium" if avg <= 2.75 else "low"
    return {"geographical": score_geo, "temporal": score_time, "technological": score_tech,
            "reliability": score_rel, "score": round(avg, 2), "label": label, "note": note}


def add(key: str, *, category: str, activity: str, subcategory: str, value: float, activity_unit: str,
        geography: str, reporting_year: str, source_id: str, dataset_version: str, source_reference: str,
        system_boundary: str, gases: str, methodology: str, dq: dict, uncertainty: str = "not quantified by source",
        active: bool = True, derivation: dict | None = None, gas_basis: str = "CO2e", extra: dict | None = None):
    s = src(source_id)
    rec = {
        "factor_id": f"{key}@{dataset_version}",
        "factor_key": key,
        "category": category,
        "activity": activity,
        "subcategory": subcategory,
        "emission_factor": round(float(value), 8),
        "unit": f"kg CO2e/{activity_unit}" if gas_basis == "CO2e" else f"kg CO2/{activity_unit}",
        "activity_unit": activity_unit,
        "gas_basis": gas_basis,
        "geography": geography,
        "reporting_year": reporting_year,
        "source_id": source_id,
        "source_name": s["name"],
        "source_publisher": s["publisher"],
        "source_url": s["url"],
        "source_landing_page": s.get("landing_page"),
        "source_reference": source_reference,
        "dataset_version": dataset_version,
        "system_boundary": system_boundary,
        "greenhouse_gases_included": gases,
        "methodology": methodology,
        "derivation": derivation,
        "data_quality": dq,
        "uncertainty": uncertainty,
        "licence": s["licence"],
        "last_updated": TODAY,
        "is_active": active,
    }
    if extra:
        rec.update(extra)
    FACTORS.append(rec)
    return rec


# =========================================================================== DESNZ
def load_desnz(fname: str) -> pd.DataFrame:
    df = pd.read_excel(RAW / "transportation" / fname, sheet_name="Factors by Category", header=5)
    df = df.iloc[:, :10]
    df.columns = ["ID", "Scope", "L1", "L2", "L3", "L4", "Col", "UOM", "GHG", "F"]
    for c in ["L1", "L2", "L3", "L4", "Col", "UOM", "GHG"]:
        df[c] = df[c].astype("string").str.strip()
    return df


def dz(df: pd.DataFrame, L1: str, L2: str, L3: str, uom: str, L4: str | None = None, col: str | None = None,
       ghg: str = "kg CO2e") -> tuple[float, str]:
    q = (df.L1 == L1) & (df.L2 == L2) & (df.L3 == L3) & (df.UOM == uom) & (df.GHG == ghg)
    q &= df.L4.isna() if L4 is None else (df.L4 == L4)
    q &= df.Col.isna() if col is None else (df.Col == col)
    m = df[q]
    if len(m) != 1 or pd.isna(m.F.iloc[0]):
        raise KeyError(f"DESNZ lookup failed ({len(m)} rows): {L1} | {L2} | {L3} | {L4} | {col} | {uom} | {ghg}")
    return float(m.F.iloc[0]), str(m.ID.iloc[0])


DESNZ_BOUNDARY_TTW = ("Direct (tank-to-wheel / point-of-use) emissions; excludes well-to-tank (fuel supply chain), "
                      "vehicle manufacture and infrastructure.")


def build_desnz(df: pd.DataFrame, sid: str, ver: str, year: str, active: bool):
    D = lambda *a, **k: dz(df, *a, **k)  # noqa: E731
    yr_gap = 1 if active else 2

    # ------------------------------------------------------------ flights
    flight_sets = {
        "domestic_uk": ("Domestic, to/from UK", ["Average passenger"]),
        "short_haul_uk": ("Short-haul, to/from UK", ["Average passenger", "Economy class", "Business class"]),
        "long_haul_uk": ("Long-haul, to/from UK", ["Average passenger", "Economy class", "Premium economy class",
                                                    "Business class", "First class"]),
        "international_non_uk": ("International, to/from non-UK", ["Average passenger", "Economy class",
                                                                  "Premium economy class", "Business class", "First class"]),
    }
    cls_key = {"Average passenger": "average", "Economy class": "economy", "Premium economy class": "premium_economy",
               "Business class": "business", "First class": "first"}
    for band, (L3, classes) in flight_sets.items():
        for c in classes:
            for rf, col in (("with_rf", "With RF"), ("without_rf", "Without RF")):
                v, fid = D("Business travel- air", "Flights", L3, "passenger.km", L4=c, col=col)
                add(f"transport.flight.{band}.{cls_key[c]}.{rf}", category="transportation", activity="Air travel",
                    subcategory=f"{L3} - {c} ({col})", value=v, activity_unit="passenger.km",
                    geography="UK-registered/UK-route basis; non-UK international set from DfT/Innovata analysis",
                    reporting_year=year, source_id=sid, dataset_version=ver, source_reference=f"DESNZ ID {fid}",
                    system_boundary=("Direct fuel combustion (CO2, CH4, N2O). Includes 8% great-circle distance uplift. "
                                     + ("Includes radiative-forcing multiplier (1.7 on CO2) for non-CO2 climate effects."
                                        if rf == "with_rf" else "Excludes non-CO2 radiative forcing effects.")),
                    gases="CO2, CH4, N2O" + (" + RF uplift" if rf == "with_rf" else ""),
                    methodology="DESNZ aviation methodology (EUROCONTROL small emitters tool; CAA load factors; seat-area class allocation).",
                    dq=quality(3 if band == "international_non_uk" else 3, yr_gap, 2, 1,
                               "Official government dataset; route mix is UK-centric, used as international proxy."),
                    active=active)

    # ------------------------------------------------------------ rail / bus / taxi / motorbike (pkm & vkm)
    for key, L2, L3, uom in [
        ("transport.rail.national.uk", "Rail", "National rail", "passenger.km"),
        ("transport.rail.international", "Rail", "International rail", "passenger.km"),
        ("transport.rail.light_rail_tram", "Rail", "Light rail and tram", "passenger.km"),
        ("transport.rail.underground", "Rail", "London Underground", "passenger.km"),
        ("transport.bus.local_average.uk", "Bus", "Average local bus", "passenger.km"),
        ("transport.bus.coach.uk", "Bus", "Coach", "passenger.km"),
        ("transport.taxi.regular.uk.pkm", "Taxis", "Regular taxi", "passenger.km"),
        ("transport.taxi.regular.uk.vkm", "Taxis", "Regular taxi", "km"),
    ]:
        v, fid = D("Business travel- land", L2, L3, uom)
        au = "vehicle.km" if uom == "km" else uom
        add(key, category="transportation", activity=L2, subcategory=L3, value=v, activity_unit=au,
            geography="United Kingdom", reporting_year=year, source_id=sid, dataset_version=ver,
            source_reference=f"DESNZ ID {fid}", system_boundary=DESNZ_BOUNDARY_TTW + (" Rail includes electricity generation for electric traction." if L2 == "Rail" else ""),
            gases="CO2, CH4, N2O", methodology="DESNZ passenger land transport methodology (average UK occupancy / load factors).",
            dq=quality(3, yr_gap, 2, 1, "Official UK dataset used as international proxy outside the UK."), active=active)

    for size in ["Small", "Medium", "Large", "Average"]:
        v, fid = D("Business travel- land", "Motorbike", size, "km")
        add(f"transport.motorbike.{size.lower()}.uk", category="transportation", activity="Motorbike",
            subcategory=f"{size} motorbike", value=v, activity_unit="vehicle.km", geography="United Kingdom",
            reporting_year=year, source_id=sid, dataset_version=ver, source_reference=f"DESNZ ID {fid}",
            system_boundary=DESNZ_BOUNDARY_TTW, gases="CO2, CH4, N2O", methodology="DESNZ motorbike methodology.",
            dq=quality(3, yr_gap, 2, 1, "UK fleet; proxy elsewhere."), active=active)

    car_fuels = {"Diesel": "diesel", "Petrol": "petrol", "Hybrid": "hybrid", "CNG": "cng", "LPG": "lpg",
                 "Unknown": "unknown", "Plug-in Hybrid Electric Vehicle": "phev", "Battery Electric Vehicle": "bev"}
    for size in ["Small car", "Medium car", "Large car", "Average car"]:
        for col, fk in car_fuels.items():
            try:
                v, fid = D("Business travel- land", "Cars (by size)", size, "km", col=col)
            except KeyError:
                continue  # DESNZ publishes no value for this combination (e.g. small CNG car)
            add(f"transport.car.{size.split()[0].lower()}.{fk}.uk", category="transportation", activity="Car",
                subcategory=f"{size} - {col}", value=v, activity_unit="vehicle.km", geography="United Kingdom",
                reporting_year=year, source_id=sid, dataset_version=ver, source_reference=f"DESNZ ID {fid}",
                system_boundary=DESNZ_BOUNDARY_TTW + (" BEV/PHEV electric share uses UK grid electricity." if fk in ("bev", "phev") else ""),
                gases="CO2, CH4, N2O", methodology="DESNZ car factors: SMMT registrations, real-world uplift on type-approval CO2.",
                dq=quality(3, yr_gap, 2, 1, "UK fleet; proxy elsewhere."), active=active)
    # EV electricity consumption (kWh per vehicle-km) - used to build country-specific EV factors
    for size in ["Small car", "Medium car", "Large car", "Average car"]:
        v, fid = D("SECR kWh UK electricity for EVs", "Cars (by size)", size, "km", col="Battery Electric Vehicle", ghg="kWh (net)")
        FACTORS.append({"factor_id": f"param.ev_kwh_per_km.{size.split()[0].lower()}@{ver}",
                        "factor_key": f"param.ev_kwh_per_km.{size.split()[0].lower()}", "category": "parameter",
                        "activity": "EV electricity consumption", "subcategory": f"{size} BEV", "emission_factor": v,
                        "unit": "kWh/vehicle.km", "activity_unit": "vehicle.km", "gas_basis": "n/a",
                        "geography": "United Kingdom fleet", "reporting_year": year, "source_id": sid,
                        "source_name": registry[sid]["name"], "source_publisher": registry[sid]["publisher"],
                        "source_url": registry[sid]["url"], "source_landing_page": registry[sid].get("landing_page"),
                        "source_reference": f"DESNZ ID {fid}", "dataset_version": ver,
                        "system_boundary": "Electricity drawn from the grid per km (SECR kWh table).", "greenhouse_gases_included": "n/a",
                        "methodology": "DESNZ EV methodology (real-world consumption).", "derivation": None,
                        "data_quality": quality(3, yr_gap, 2, 1, "UK EV fleet energy use, used as proxy."),
                        "uncertainty": "not quantified by source", "licence": registry[sid]["licence"],
                        "last_updated": TODAY, "is_active": active})

    # ------------------------------------------------------------ fuels (stationary: generators, cooking)
    for key, L2, L3, uom, au in [
        ("energy.fuel.diesel.litre", "Liquid fuels", "Diesel (100% mineral diesel)", "litres", "litre"),
        ("energy.fuel.petrol.litre", "Liquid fuels", "Petrol (100% mineral petrol)", "litres", "litre"),
        ("energy.fuel.lpg.litre", "Gaseous fuels", "LPG", "litres", "litre"),
        ("energy.fuel.lpg.tonne", "Gaseous fuels", "LPG", "tonnes", "tonne"),
        ("energy.fuel.natural_gas.m3", "Gaseous fuels", "Natural gas (100% mineral blend)", "cubic metres", "m3"),
        ("energy.fuel.natural_gas.kwh", "Gaseous fuels", "Natural gas (100% mineral blend)", "kWh (Net CV)", "kWh (net CV)"),
    ]:
        v, fid = D("Fuels", L2, L3, uom)
        add(key, category="energy", activity="Stationary fuel combustion", subcategory=L3, value=v, activity_unit=au,
            geography="Fuel property based (applicable internationally; UK fuel specification)", reporting_year=year,
            source_id=sid, dataset_version=ver, source_reference=f"DESNZ ID {fid}",
            system_boundary="Scope 1 combustion emissions only; excludes well-to-tank.", gases="CO2, CH4, N2O",
            methodology="DESNZ fuel factors from UK GHG Inventory (IPCC 2006 based) and fuel calorific values.",
            dq=quality(2, yr_gap, 2, 1, "Fuel-chemistry based factors transfer well between countries."), active=active)
    # UK grid electricity
    v, fid = D("UK electricity", "Electricity generated", "Electricity: UK", "kWh", L4="kWh")
    add("electricity.grid.GB", category="energy", activity="Grid electricity", subcategory="UK grid (location-based)",
        value=v, activity_unit="kWh", geography="United Kingdom", reporting_year=year, source_id=sid,
        dataset_version=ver, source_reference=f"DESNZ ID {fid}",
        system_boundary="Generation emissions (Scope 2, location-based). Excludes T&D losses and well-to-tank.",
        gases="CO2, CH4, N2O", methodology="DESNZ UK grid average (DUKES generation mix).",
        dq=quality(1, yr_gap, 1, 1, "Official national grid factor."), active=active)

    # ------------------------------------------------------------ hotel stay
    hotel = df[(df.L1 == "Hotel stay") & (df.GHG == "kg CO2e") & df.F.notna()]
    for _, r in hotel.iterrows():
        country = str(r.L3)
        slug = re.sub(r"[^a-z0-9]+", "_", country.lower()).strip("_")
        add(f"accommodation.hotel.{slug}", category="accommodation", activity="Hotel stay",
            subcategory=f"Hotel room-night - {country}", value=float(r.F), activity_unit="room.night",
            geography=country, reporting_year="CHSB 2021 benchmark (held constant since 2022 DESNZ set)",
            source_id=sid, dataset_version=ver, source_reference=f"DESNZ ID {r.ID} (from Cornell CHSB Index 2021)",
            system_boundary="Hotel operational energy (Scope 1+2 of the hotel) allocated per occupied room-night; excludes food, laundry outsourcing and embodied emissions.",
            gases="CO2e (AR4 or AR5 depending on reporting hotels)",
            methodology="Cornell Hotel Sustainability Benchmarking Index median per country, all hotel classes (DESNZ methodology section 11).",
            dq=quality(1, 3, 2, 2, "Country-specific benchmark; hotel class not differentiated; 2021 data."), active=active,
            extra={"country": country})

    # ------------------------------------------------------------ materials (cradle-to-gate, per tonne)
    mats = [
        ("materials.paper.virgin", "Paper", "Paper and board: paper", "Primary material production", "Virgin paper"),
        ("materials.paper.recycled", "Paper", "Paper and board: paper", "Closed-loop source", "Recycled-content paper"),
        ("materials.board.virgin", "Paper", "Paper and board: board", "Primary material production", "Cardboard / board (virgin)"),
        ("materials.board.recycled", "Paper", "Paper and board: board", "Closed-loop source", "Cardboard / board (recycled)"),
        ("materials.plastic.pvc", "Plastic", "Plastics: PVC (incl. forming)", "Primary material production", "PVC (banners, ID cards)"),
        ("materials.plastic.pvc.recycled", "Plastic", "Plastics: PVC (incl. forming)", "Closed-loop source", "PVC recycled content"),
        ("materials.plastic.pet", "Plastic", "Plastics: PET (incl. forming)", "Primary material production", "PET (bottles; polyester polymer proxy)"),
        ("materials.plastic.pet.recycled", "Plastic", "Plastics: PET (incl. forming)", "Closed-loop source", "rPET recycled content"),
        ("materials.plastic.pp", "Plastic", "Plastics: PP (incl. forming)", "Primary material production", "Polypropylene (non-woven bags, folders)"),
        ("materials.plastic.average", "Plastic", "Plastics: average plastics", "Primary material production", "Average plastics"),
        ("materials.plastic.film", "Plastic", "Plastics: average plastic film", "Primary material production", "Plastic film / packaging"),
        ("materials.textile.clothing", "Other", "Clothing", "Primary material production", "Textiles (cotton bags, fabric banners, T-shirts)"),
        ("materials.textile.reused", "Other", "Clothing", "Re-used", "Re-used textiles"),
        ("materials.glass", "Other", "Glass", "Primary material production", "Glass"),
        ("materials.metal.aluminium", "Metal", "Metal: aluminium cans and foil (excl. forming)", "Primary material production", "Aluminium"),
        ("materials.metal.steel", "Metal", "Metal: steel cans", "Primary material production", "Steel"),
    ]
    for key, L2, L3, col, label in mats:
        v, fid = D("Material use", L2, L3, "tonnes", col=col)
        add(key, category="materials", activity="Purchased materials", subcategory=label, value=v / 1000.0,
            activity_unit="kg", geography="United Kingdom (proxy)", reporting_year=year, source_id=sid, dataset_version=ver,
            source_reference=f"DESNZ ID {fid} ({col}); converted from kg CO2e/tonne",
            system_boundary="Cradle-to-gate material production (extraction, processing, manufacture). Excludes use phase and end-of-life (end-of-life is reported under Waste).",
            gases="CO2, CH4, N2O (CO2e)", methodology="DESNZ material use factors (WRAP / ICE-based life cycle data).",
            derivation={"formula": "kg CO2e/tonne / 1000", "original_value": v, "original_unit": "kg CO2e/tonne"},
            dq=quality(3, yr_gap, 3, 2, "UK production proxy; product-level processing (printing, sewing) excluded."), active=active)

    # ------------------------------------------------------------ waste disposal (per tonne -> per kg)
    wastes = {
        "food": "Organic: food and drink waste", "paper": "Paper and board: paper", "cardboard": "Paper and board: board",
        "plastic": "Plastics: average plastics", "glass": "Glass", "metal": "Metal: mixed cans",
        "mixed": "Commercial and industrial waste", "textiles": "Clothing",
    }
    routes = {"Landfill": "landfill", "Combustion": "incineration", "Composting": "composting",
              "Anaerobic digestion": "anaerobic_digestion", "Closed-loop": "recycling", "Open-loop": "recycling_open_loop"}
    for wk, L3 in wastes.items():
        L2 = df[(df.L1 == "Waste disposal") & (df.L3 == L3)].L2.dropna().unique()
        if len(L2) == 0:
            continue
        for col, rk in routes.items():
            try:
                v, fid = D("Waste disposal", str(L2[0]), L3, "tonnes", col=col)
            except KeyError:
                continue
            add(f"waste.{wk}.{rk}", category="waste", activity="Waste disposal", subcategory=f"{L3} - {col}",
                value=v / 1000.0, activity_unit="kg", geography="United Kingdom (proxy)", reporting_year=year,
                source_id=sid, dataset_version=ver, source_reference=f"DESNZ ID {fid}; converted from kg CO2e/tonne",
                system_boundary=("GHG Protocol Scope 3 Cat.5 'cut-off' approach: recycling/combustion/composting carry only collection and "
                                 "transport to the treatment site (benefits of recycling or energy recovery are not credited). "
                                 "Landfill includes methane from decomposition with UK landfill-gas capture rates."),
                gases="CO2e (fossil CO2, CH4, N2O; biogenic CO2 excluded)",
                methodology="DESNZ waste disposal methodology (UK landfill FOD model).",
                derivation={"formula": "kg CO2e/tonne / 1000", "original_value": v, "original_unit": "kg CO2e/tonne"},
                dq=quality(4 if rk == "landfill" else 3, yr_gap, 3, 1,
                           "UK landfill gas capture is higher than typical Indian open dumps/landfills, so Indian landfill emissions are likely UNDER-estimated."
                           if rk == "landfill" else "Transport-only factor under cut-off method."), active=active)

    # ------------------------------------------------------------ water
    for key, L1, au, uom in [("water.supply", "Water supply", "m3", "cubic metres"), ("water.treatment", "Water treatment", "m3", "cubic metres")]:
        v, fid = D(L1, L1, L1, uom)
        add(key, category="food", activity=L1, subcategory=L1, value=v, activity_unit=au, geography="United Kingdom (proxy)",
            reporting_year=year, source_id=sid, dataset_version=ver, source_reference=f"DESNZ ID {fid}",
            system_boundary="Utility treatment and distribution energy.", gases="CO2, CH4, N2O",
            methodology="DESNZ water methodology (Water UK).", dq=quality(4, yr_gap, 3, 1, "UK utilities; proxy only."), active=active)


def desnz_co2_ratio(df: pd.DataFrame, *args, **kw) -> tuple[float, str, str]:
    """CO2e / CO2 ratio for a DESNZ factor - used to convert CO2-only factors to CO2e."""
    tot, fid1 = dz(df, *args, **kw)
    co2, fid2 = dz(df, *args, ghg="kg CO2e of CO2 per unit", **kw)
    return tot / co2, fid1, fid2


# =========================================================================== CEA (INDIA GRID)
def build_cea():
    sid = "CEA_BASELINE_V22_XLSX"
    xls = RAW / "electricity" / "CEA_CO2_Baseline_Database_v22.0.xlsx"
    res = pd.read_excel(xls, sheet_name="Results", header=None)
    # locate cells by label (layout-independent)
    def find_cell(pred):
        for i in range(len(res)):
            for j in range(res.shape[1]):
                v = res.iat[i, j]
                if isinstance(v, str) and pred(v.strip()):
                    return i, j
        raise SystemExit("CEA Results sheet layout not recognised")
    is_year = lambda v: bool(re.fullmatch(r"20\d\d-\d\d", str(v).strip()))  # noqa: E731
    hdr_r, ex_c = find_cell(lambda v: v.startswith("Emission Factors (tCO2/MWh) (excl. Imports)"))
    _, inc_c = find_cell(lambda v: v.startswith("Emission Factors (tCO2/MWh) (incl. Imports)"))
    ex_cols = [c for c in range(ex_c + 1, inc_c) if is_year(res.iat[hdr_r, c])]
    in_cols = [c for c in range(inc_c + 1, res.shape[1]) if is_year(res.iat[hdr_r, c])]
    row_excl, _ = find_cell(lambda v: v == "Weighted Average Grid Emission Rate (Incl. RES,Captive)")
    row_incl, _ = find_cell(lambda v: v == "Weighted Average Grid Emission Rate (Incl. RES,Captive) (2)")
    in_map = {str(res.iat[hdr_r, c]).strip(): c for c in in_cols}
    series = []
    for c in ex_cols:
        y = str(res.iat[hdr_r, c]).strip()
        v_in = float(res.iat[row_incl, in_map[y]]) if y in in_map and pd.notna(res.iat[row_incl, in_map[y]]) else None
        series.append({"fiscal_year": y, "weighted_avg_incl_RE_captive_excl_imports_tCO2_per_MWh": float(res.iat[row_excl, c]),
                       "weighted_avg_incl_RE_captive_incl_imports_tCO2_per_MWh": v_in})
    # cross-check with the PDF Annexure-I values (cross-border adjusted), parsed from the user guide
    pdf_vals = {}
    with pdfplumber.open(RAW / "electricity" / "CEA_CO2_Baseline_User_Guide_v22.0_Aug2026.pdf") as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    for m in re.finditer(r"(20\d\d-\d\d)\*?\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(0\.\d{3})", text):
        pdf_vals[m.group(1)] = {"total_co2_Mt": float(m.group(2)), "net_gen_conventional_BU": float(m.group(3)),
                                "re_gen_BU": float(m.group(4)), "total_net_gen_BU": float(m.group(5)),
                                "weighted_avg_tCO2_per_MWh": float(m.group(6))}
    for s in series:
        s["user_guide_annexure_I_tCO2_per_MWh"] = pdf_vals.get(s["fiscal_year"], {}).get("weighted_avg_tCO2_per_MWh")
    out = PROC / "electricity"
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(series).to_csv(out / "india_grid_emission_factor_series_CEA_v22.csv", index=False)
    (out / "cea_v22_annexure_I_parsed.json").write_text(json.dumps(pdf_vals, indent=2))

    # Generation mix FY2025-26 from station-level Data sheet
    data = pd.read_excel(xls, sheet_name="Data", header=0)
    gen_col = next(c for c in data.columns if str(c).startswith("2025-26") and "Net" in str(c) and "Generation" in str(c))
    data["FUEL 1"] = data["FUEL 1"].fillna(data["TYPE"]).astype(str).str.strip().str.upper()
    data["TYPE"] = data["TYPE"].astype(str).str.strip().str.upper()
    # unit rows are listed with a station-total row (UNIT_NO 0) - use station totals only to avoid double counting
    st = data[data["UNIT_NO"] == 0]
    mix = st.groupby(["TYPE", "FUEL 1"])[gen_col].sum().reset_index().rename(columns={gen_col: "net_generation_GWh"})
    def rv(label):
        r, c0 = find_cell(lambda v: v.startswith(label))
        gen_hdr = max(i for i in range(r) if any(str(res.iat[i, j]).strip() == "2025-26" for j in range(res.shape[1])))
        col = next(j for j in range(c0, res.shape[1]) if str(res.iat[gen_hdr, j]).strip() == "2025-26")
        return float(res.iat[r, col])
    extra = pd.DataFrame([
        {"TYPE": "RENEWABLE (non-hydro, per CEA Results sheet)", "FUEL 1": "RES", "net_generation_GWh": rv("Net Renewable Generation")},
        {"TYPE": "IMPORT", "FUEL 1": "IMPORT", "net_generation_GWh": rv("Net Import")},
        {"TYPE": "CAPTIVE INJECTED", "FUEL 1": "CAPTIVE", "net_generation_GWh": rv("Captive power Injected into grid")},
    ])
    mix = pd.concat([mix, extra], ignore_index=True)
    mix["share_pct"] = (100 * mix.net_generation_GWh / mix.net_generation_GWh.sum()).round(2)
    mix.to_csv(out / "india_generation_mix_FY2025-26.csv", index=False)

    latest = series[-1]
    assert latest["fiscal_year"] == "2025-26", latest
    v_guide = latest["user_guide_annexure_I_tCO2_per_MWh"]
    if v_guide is None:
        raise SystemExit("Could not parse CEA Annexure-I value for 2025-26 from the user guide")

    # CO2 -> CO2e adjustment using IPCC default CH4/N2O for coal combustion (dominant grid fuel)
    ratio = (IPCC_COAL_EF["CO2"] + IPCC_COAL_EF["CH4"] * GWP_AR5["CH4"] + IPCC_COAL_EF["N2O"] * GWP_AR5["N2O"]) / IPCC_COAL_EF["CO2"]
    common = dict(category="energy", activity="Grid electricity", geography="India (single national grid)",
                  source_id="CEA_BASELINE_V22_GUIDE", dataset_version="CEA-v22.0",
                  system_boundary=("Weighted average CO2 emission of all grid-connected generation incl. renewables and captive injection, "
                                   "adjusted for cross-border transfers (net generation basis). Scope 2 location-based. "
                                   "Excludes T&D losses and upstream fuel supply."),
                  methodology="CEA CO2 Baseline Database v22.0 (ACM0002 / Grid Tool v7.0); Annexure-I weighted average.")
    add("electricity.grid.IN.co2", subcategory="India grid weighted average - CO2 only (as published)", value=v_guide,
        activity_unit="kWh", reporting_year="FY 2025-26", source_reference="User Guide v22.0, Annexure-I (2025-26 row); cross-checked with database workbook 'Results' sheet",
        gases="CO2 only", gas_basis="CO2", dq=quality(1, 1, 1, 1, "Official Government of India factor, latest year."),
        derivation={"note": "tCO2/MWh is numerically equal to kg CO2/kWh", "workbook_excl_imports": latest["weighted_avg_incl_RE_captive_excl_imports_tCO2_per_MWh"],
                    "workbook_incl_imports": latest["weighted_avg_incl_RE_captive_incl_imports_tCO2_per_MWh"]},
        uncertainty="CEA does not publish an uncertainty range", **common)
    add("electricity.grid.IN", subcategory="India grid weighted average - CO2e (CO2 + IPCC default CH4/N2O)", value=v_guide * ratio,
        activity_unit="kWh", reporting_year="FY 2025-26",
        source_reference="CEA v22.0 Annexure-I x IPCC 2006 Vol.2 Table 2.2 CH4/N2O adjustment",
        gases="CO2, CH4, N2O (CH4/N2O estimated)",
        dq=quality(1, 1, 1, 1, "Official CO2 factor; CH4+N2O added via IPCC defaults (+0.45%)."),
        derivation={"formula": "EF_CO2 x (94600 + 1x28 + 1.5x265) / 94600",
                    "inputs": {"EF_CO2_kg_per_kWh": v_guide, "IPCC_2006_coal_kg_per_TJ": IPCC_COAL_EF, "GWP_AR5": GWP_AR5},
                    "ratio": round(ratio, 6)},
        uncertainty="CEA does not publish an uncertainty range", **common)
    # historical (inactive) years for version history / reproducibility
    for s in series[:-1]:
        v = s["user_guide_annexure_I_tCO2_per_MWh"]
        if v is None:
            continue
        add(f"electricity.grid.IN.FY{s['fiscal_year']}", subcategory=f"India grid weighted average CO2e - FY {s['fiscal_year']} (historical)",
            value=v * ratio, activity_unit="kWh", reporting_year=f"FY {s['fiscal_year']}",
            source_reference="CEA v22.0 Annexure-I historical series x IPCC CH4/N2O adjustment", gases="CO2, CH4, N2O (CH4/N2O estimated)",
            dq=quality(1, 3, 1, 1, "Historical year - use only to reproduce past-year events."),
            derivation={"formula": "EF_CO2 x ratio", "EF_CO2": v, "ratio": round(ratio, 6)}, active=True, **common)
    return ratio


# =========================================================================== INDIA GHG PROGRAM (road + rail)
def parse_indiaghgp_road() -> list[dict]:
    """Extract the passenger-car / two-wheeler / three-wheeler / bus table from the 2015 technical paper."""
    with pdfplumber.open(RAW / "transportation" / "IndiaGHGP_Road_Transport_Technical_Paper_v1.0_2015.pdf") as pdf:
        text = "\n".join((pdf.pages[i].extract_text() or "") for i in (10, 11))
    rows = []
    for m in re.finditer(r"^\s*(\d+)\s+(Scooter|Motorcycle)\s+<(\d+)\s*CC\s+([\d.]+)\s+([\d.]+)", text, re.M):
        rows.append({"group": "two_wheeler", "type": m.group(2), "engine": f"<{m.group(3)} CC", "fuel": "Gasoline",
                     "kgCO2_per_km": float(m.group(4)), "kgCO2_per_km_uplift": float(m.group(5))})
    for m in re.finditer(r"^\s*\d\s+(Petrol|Diesel|CNG)\s+(0\.\d+)\s*$", text, re.M):
        rows.append({"group": "three_wheeler", "type": "Auto-rickshaw", "engine": "", "fuel": m.group(1),
                     "kgCO2_per_km": float(m.group(2)), "kgCO2_per_km_uplift": None})
    for m in re.finditer(r"^\s*(\d+)\s+([A-Za-z][A-Za-z ]*?)\s+([<>]?\s?\d{3,4}\s?CC|-)\s+(Gasoline|Diesel|CNG|LPG)\s+([\d.]+)\s+([\d.]+)", text, re.M):
        rows.append({"group": "car", "type": m.group(2).strip(), "engine": m.group(3).replace(" ", ""), "fuel": m.group(4),
                     "kgCO2_per_km": float(m.group(5)), "kgCO2_per_km_uplift": float(m.group(6))})
    m = re.search(r"bus transport is\s+([\d.]+)\s*kg", text)
    if m:
        rows.append({"group": "bus", "type": "City bus (intracity)", "engine": "", "fuel": "Diesel",
                     "kgCO2_per_pkm": float(m.group(1))})
    # "Premium Hatchback" spans two lines in the PDF; handle the orphaned row 6
    if not any(r["group"] == "car" and r["engine"] == "<1600CC" and r["type"].endswith("Hatchback") and r["fuel"] == "Gasoline" for r in rows):
        m = re.search(r"^\s*6\s+Hatchback\s+<1600\s*CC\s+Gasoline\s+([\d.]+)\s+([\d.]+)", text, re.M)
        if m:
            rows.append({"group": "car", "type": "Premium Hatchback", "engine": "<1600CC", "fuel": "Gasoline",
                         "kgCO2_per_km": float(m.group(1)), "kgCO2_per_km_uplift": float(m.group(2))})
    return rows


def parse_indiaghgp_rail() -> dict:
    with pdfplumber.open(RAW / "transportation" / "IndiaGHGP_Rail_Transport_Emission_v1.0_2015.pdf") as pdf:
        text = pdf.pages[7].extract_text() or ""
    # PDF text renders as "1.N on-Suburban - 0.00794 ... 2.S uburban – 0.00795" for 2012-13 then 2014-15
    vals = re.findall(r"[-\u2013]\s*(0\.00\d+)", text)
    if len(vals) < 4:
        raise SystemExit(f"Rail factor table not recognised: {vals}")
    return {"non_suburban_2012_13": float(vals[0]), "suburban_2012_13": float(vals[1]),
            "non_suburban_2014_15": float(vals[2]), "suburban_2014_15": float(vals[3]),
            "unit": "kg CO2 / passenger-km", "page": 8}


def build_india_transport(df26: pd.DataFrame):
    rows = parse_indiaghgp_road()
    out = PROC / "transportation"
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out / "india_ghgp_road_factors_extracted.csv", index=False)
    rail = parse_indiaghgp_rail()
    (out / "india_ghgp_rail_factors_extracted.json").write_text(json.dumps(rail, indent=2))

    def find(group, typ, engine, fuel):
        for r in rows:
            if r["group"] == group and r["type"] == typ and r["engine"] == engine and r["fuel"] == fuel:
                return r
        raise KeyError((group, typ, engine, fuel))

    sid_road, ver_road = "INDIAGHGP_ROAD_2015", "IndiaGHGP-Road-v1.0-2015"
    road_dq = quality(1, 4, 2, 2, "India-specific (WRI/CII/TERI) but 2015 consultation draft; CO2-only converted to CO2e.")
    # car segments: (key, type, engine, fuel, DESNZ analogue fuel for CO2e ratio)
    car_map = [
        ("transport.car.hatchback.petrol.IN", "Hatchback", "<1400CC", "Gasoline", "Petrol", "Hatchback petrol (<1400 cc)"),
        ("transport.car.hatchback.diesel.IN", "Hatchback", "<1400CC", "Diesel", "Diesel", "Hatchback diesel (<1400 cc)"),
        ("transport.car.sedan.petrol.IN", "Sedan", "<1600CC", "Gasoline", "Petrol", "Sedan petrol (<1600 cc)"),
        ("transport.car.sedan.diesel.IN", "Sedan", "<1600CC", "Diesel", "Diesel", "Sedan diesel (<1600 cc)"),
        ("transport.car.suv.petrol.IN", "SUV", "<3000CC", "Gasoline", "Petrol", "SUV petrol (<3000 cc)"),
        ("transport.car.suv.diesel.IN", "SUV", "<2500CC", "Diesel", "Diesel", "SUV diesel (<2500 cc)"),
        ("transport.car.muv.diesel.IN", "MUV", "<2500CC", "Diesel", "Diesel", "MUV / MPV diesel (<2500 cc)"),
        ("transport.car.hybrid.petrol.IN", "Hybrid", "<2000CC", "Gasoline", "Hybrid", "Hybrid petrol (<2000 cc)"),
        ("transport.car.small.cng.IN", "Small", "<800CC", "CNG", "CNG", "Small car CNG (<800 cc)"),
    ]
    for key, typ, eng, fuel, dfuel, label in car_map:
        r = find("car", typ, eng, fuel)
        ratio, f1, f2 = desnz_co2_ratio(df26, "Business travel- land", "Cars (by size)", "Average car", "km", col=dfuel)
        add(key, category="transportation", activity="Car", subcategory=label, value=r["kgCO2_per_km_uplift"] * ratio,
            activity_unit="vehicle.km", geography="India", reporting_year="2015", source_id=sid_road, dataset_version=ver_road,
            source_reference="India GHG Program Road Transport Technical Paper v1.0 (2015), Summary of Emission Factors (pp. 9-10)",
            system_boundary="Tank-to-wheel fuel combustion; includes 10% real-world uplift over type-approval CO2.",
            gases="CO2 (published) + CH4/N2O via DESNZ ratio", methodology="Fuel-efficiency based (manufacturer-declared km/l x fuel EF) with 10% uplift.",
            derivation={"formula": "kgCO2/km (with 10% uplift) x DESNZ CO2e/CO2 ratio for analogous car fuel",
                        "published_kgCO2_per_km_uplift": r["kgCO2_per_km_uplift"], "published_kgCO2_per_km": r["kgCO2_per_km"],
                        "ratio": round(ratio, 6), "ratio_source": f"DESNZ 2026 IDs {f1} / {f2}"},
            dq=road_dq)
    for key, typ, eng, label in [("transport.motorbike.scooter.IN", "Scooter", "<110 CC", "Scooter (<110 cc)"),
                                 ("transport.motorbike.small.IN", "Motorcycle", "<125 CC", "Motorcycle (<125 cc)"),
                                 ("transport.motorbike.medium.IN", "Motorcycle", "<200 CC", "Motorcycle (<200 cc)"),
                                 ("transport.motorbike.large.IN", "Motorcycle", "<500 CC", "Motorcycle (<500 cc)")]:
        r = find("two_wheeler", typ, eng, "Gasoline")
        ratio, f1, f2 = desnz_co2_ratio(df26, "Business travel- land", "Motorbike", "Average", "km")
        add(key, category="transportation", activity="Motorcycle", subcategory=label, value=r["kgCO2_per_km_uplift"] * ratio,
            activity_unit="vehicle.km", geography="India", reporting_year="2015", source_id=sid_road, dataset_version=ver_road,
            source_reference="India GHG Program Road Transport Technical Paper v1.0 (2015), Two Wheelers table",
            system_boundary="Tank-to-wheel; 10% real-world uplift.", gases="CO2 (published) + CH4/N2O via DESNZ ratio",
            methodology="Fuel-efficiency based with 10% uplift.",
            derivation={"formula": "kgCO2/km (uplift) x DESNZ motorbike CO2e/CO2 ratio", "published": r["kgCO2_per_km_uplift"],
                        "ratio": round(ratio, 6), "ratio_source": f"DESNZ 2026 IDs {f1} / {f2}"}, dq=road_dq)
    for fuel in ["Petrol", "Diesel", "CNG"]:
        r = find("three_wheeler", "Auto-rickshaw", "", fuel)
        dfuel = {"Petrol": "Petrol", "Diesel": "Diesel", "CNG": "CNG"}[fuel]
        ratio, f1, f2 = desnz_co2_ratio(df26, "Business travel- land", "Cars (by size)", "Average car", "km", col=dfuel)
        add(f"transport.autorickshaw.{fuel.lower()}.IN", category="transportation", activity="Auto-rickshaw",
            subcategory=f"Three-wheeler ({fuel})", value=r["kgCO2_per_km"] * ratio, activity_unit="vehicle.km", geography="India",
            reporting_year="2015", source_id=sid_road, dataset_version=ver_road,
            source_reference="India GHG Program Road Transport Technical Paper v1.0 (2015), Three Wheelers table",
            system_boundary="Tank-to-wheel; no real-world uplift published for three-wheelers.", gases="CO2 (published) + CH4/N2O via DESNZ ratio",
            methodology="Fuel-efficiency based.", derivation={"formula": "kgCO2/km x DESNZ car CO2e/CO2 ratio (same fuel)",
            "published": r["kgCO2_per_km"], "ratio": round(ratio, 6), "ratio_source": f"DESNZ 2026 IDs {f1} / {f2}"}, dq=road_dq)
    bus = next(r for r in rows if r["group"] == "bus")
    ratio, f1, f2 = desnz_co2_ratio(df26, "Business travel- land", "Bus", "Average local bus", "passenger.km")
    add("transport.bus.city.IN", category="transportation", activity="Bus", subcategory="City bus (intracity, India)",
        value=bus["kgCO2_per_pkm"] * ratio, activity_unit="passenger.km", geography="India (intracity only)", reporting_year="2015",
        source_id=sid_road, dataset_version=ver_road, source_reference="India GHG Program Road Transport Technical Paper v1.0 (2015), Bus",
        system_boundary="Tank-to-wheel; state transport undertaking fleet averages. Not applicable to intercity coaches or BRTS.",
        gases="CO2 (published) + CH4/N2O via DESNZ ratio", methodology="Fleet fuel use / passenger-km.",
        derivation={"formula": "kgCO2/pkm x DESNZ local-bus CO2e/CO2 ratio", "published": bus["kgCO2_per_pkm"], "ratio": round(ratio, 6),
                    "ratio_source": f"DESNZ 2026 IDs {f1} / {f2}"}, dq=road_dq)

    ratio, f1, f2 = desnz_co2_ratio(df26, "Business travel- land", "Rail", "National rail", "passenger.km")
    for key, val, label in [("transport.rail.national.IN", rail["non_suburban_2014_15"], "Indian Railways non-suburban"),
                            ("transport.rail.suburban.IN", rail["suburban_2014_15"], "Indian Railways suburban")]:
        add(key, category="transportation", activity="Rail", subcategory=label, value=val * ratio, activity_unit="passenger.km",
            geography="India", reporting_year="FY 2014-15", source_id="INDIAGHGP_RAIL_2015", dataset_version="IndiaGHGP-Rail-v1.0-2015",
            source_reference="India GHG Program Rail Transport Emission Factors v1.0 (2015), Executive Summary (p.7)",
            system_boundary="Traction energy (diesel + electricity at then-current grid factor) allocated by passenger-km. No class (AC/sleeper) differentiation. Not for metro/MRTS.",
            gases="CO2 (published) + CH4/N2O via DESNZ ratio", methodology="Method A: total railway energy / pkm & tkm.",
            derivation={"formula": "kgCO2/pkm x DESNZ national-rail CO2e/CO2 ratio", "published": val, "ratio": round(ratio, 6),
                        "ratio_source": f"DESNZ 2026 IDs {f1} / {f2}"},
            dq=quality(1, 4, 3, 2, "India-specific but FY2014-15 data and pre-2015 grid factor; grid has since decarbonised and electrification increased - likely conservative."))


def build_ev_factors(df26: pd.DataFrame, ver: str):
    """Country-specific BEV factors = DESNZ real-world kWh/km x national grid factor."""
    kwh = {f["factor_key"].split(".")[-1]: f for f in FACTORS if f["factor_key"].startswith("param.ev_kwh_per_km.") and f["dataset_version"] == ver}
    grid_in = next(f for f in FACTORS if f["factor_key"] == "electricity.grid.IN")
    for size in ["small", "medium", "large", "average"]:
        k = kwh[size]
        add(f"transport.car.{size}.bev.IN", category="transportation", activity="Electric vehicle", subcategory=f"{size.title()} battery-electric car charged on Indian grid",
            value=k["emission_factor"] * grid_in["emission_factor"], activity_unit="vehicle.km", geography="India (grid) / UK (vehicle efficiency)",
            reporting_year="FY 2025-26 grid; 2026 vehicle data", source_id="CEA_BASELINE_V22_GUIDE", dataset_version="CEA-v22.0+DESNZ-2026",
            source_reference=f"{k['source_reference']} x {grid_in['factor_id']}",
            system_boundary="Electricity generation for charging (Scope 2-type); excludes T&D/charging losses beyond DESNZ real-world kWh, and battery manufacture.",
            gases="CO2, CH4, N2O", methodology="Energy-based: real-world kWh/km x location-based grid factor.",
            derivation={"formula": "kWh/km x kg CO2e/kWh", "kwh_per_km": k["emission_factor"], "grid_factor": grid_in["emission_factor"],
                        "inputs": [k["factor_id"], grid_in["factor_id"]]},
            dq=quality(2, 1, 3, 2, "Indian grid factor is official; vehicle efficiency from UK fleet."))


# =========================================================================== FOOD
OWID_MAP = {
    "Beef (beef herd)": ("food.beef", "Beef (beef herd)"), "Beef (dairy herd)": ("food.beef_dairy_herd", "Beef (dairy herd)"),
    "Lamb & Mutton": ("food.mutton", "Lamb & mutton"), "Pig Meat": ("food.pork", "Pork"), "Poultry Meat": ("food.chicken", "Chicken / poultry"),
    "Fish (farmed)": ("food.fish_farmed", "Fish (farmed)"), "Prawns (farmed)": ("food.prawns_farmed", "Prawns (farmed)"),
    "Eggs": ("food.eggs", "Eggs"), "Milk": ("food.milk", "Milk / curd (dairy)"), "Cheese": ("food.cheese", "Cheese / paneer proxy"),
    "Rice": ("food.rice", "Rice"), "Wheat & Rye": ("food.wheat", "Wheat (roti, bread)"), "Maize": ("food.maize", "Maize"),
    "Barley": ("food.barley", "Barley"), "Oatmeal": ("food.oats", "Oats"), "Potatoes": ("food.potatoes", "Potatoes"),
    "Cassava": ("food.cassava", "Cassava"), "Other Pulses": ("food.pulses", "Pulses / dal"), "Peas": ("food.peas", "Peas"),
    "Groundnuts": ("food.groundnuts", "Groundnuts"), "Nuts": ("food.nuts", "Tree nuts"), "Tofu": ("food.tofu", "Tofu"),
    "Soy milk": ("food.soy_milk", "Soy milk"), "Tomatoes": ("food.tomatoes", "Tomatoes"), "Onions & Leeks": ("food.onions", "Onions"),
    "Root Vegetables": ("food.root_vegetables", "Root vegetables"), "Brassicas": ("food.brassicas", "Brassicas"),
    "Other Vegetables": ("food.vegetables", "Vegetables (other)"), "Bananas": ("food.bananas", "Bananas"),
    "Apples": ("food.apples", "Apples"), "Citrus Fruit": ("food.citrus", "Citrus fruit"), "Berries & Grapes": ("food.berries", "Berries & grapes"),
    "Other Fruit": ("food.fruit", "Fruit (other)"), "Cane Sugar": ("food.sugar_cane", "Sugar (cane)"), "Beet Sugar": ("food.sugar_beet", "Sugar (beet)"),
    "Coffee": ("food.coffee", "Coffee"), "Dark Chocolate": ("food.chocolate", "Dark chocolate"), "Wine": ("food.wine", "Wine"),
}
OIL_MAP = {"Palm Oil": ("food.oil_palm", "Palm oil"), "Soybean Oil": ("food.oil_soybean", "Soybean oil"),
           "Rapeseed Oil": ("food.oil_rapeseed", "Rapeseed / mustard oil"), "Sunflower Oil": ("food.oil_sunflower", "Sunflower oil"),
           "Olive Oil": ("food.oil_olive", "Olive oil")}
POORE_BOUNDARY = ("Farm-to-retail life cycle: land-use change, farm, animal feed, processing, transport, retail and packaging, "
                  "plus food losses along the supply chain. Excludes consumer cooking and consumer-level waste.")
POORE_METH = "Poore & Nemecek (2018) meta-analysis of ~38,700 farms / 1,600 processors; global mean, 100-year GWP (CO2, CH4, N2O)."


def build_food():
    out = PROC / "food"
    out.mkdir(parents=True, exist_ok=True)
    per_kg = pd.read_csv(RAW / "food" / "owid_ghg-per-kg-poore.csv")
    chain = pd.read_csv(RAW / "food" / "owid_food-emissions-supply-chain.csv")
    stages = [c for c in chain.columns if c not in ("Entity", "Year", "Code")]
    chain["total"] = chain[stages].sum(axis=1)
    chain.to_csv(out / "poore_nemecek_supply_chain_with_totals.csv", index=False)
    per_kg.to_csv(out / "poore_nemecek_ghg_per_kg.csv", index=False)
    vcol = [c for c in per_kg.columns if c not in ("Entity", "Year", "Code")][0]
    dq = quality(3, 3, 3, 1, "Global mean; Indian production systems may differ (e.g. rice methane, dairy).")
    for ent, (key, label) in OWID_MAP.items():
        m = per_kg[per_kg.Entity == ent]
        if m.empty:
            raise SystemExit(f"OWID entity missing: {ent}")
        stage_row = chain[chain.Entity == ent]
        breakdown = {s: round(float(stage_row[s].iloc[0]), 4) for s in stages} if not stage_row.empty else None
        add(key, category="food", activity="Food product", subcategory=label, value=float(m[vcol].iloc[0]), activity_unit="kg",
            geography="Global average", reporting_year="2010 (published 2018)", source_id="OWID_POORE_GHG_PER_KG", dataset_version="OWID-Poore2018",
            source_reference=f"OWID 'ghg-per-kg-poore', entity '{ent}'", system_boundary=POORE_BOUNDARY, gases="CO2, CH4, N2O (CO2e, GWP100)",
            methodology=POORE_METH, dq=dq, uncertainty="Large inter-producer variability (Poore & Nemecek report 10th-90th percentile ranges spanning several-fold for most products).",
            extra={"supply_chain_breakdown": breakdown})
    for ent, (key, label) in OIL_MAP.items():
        r = chain[chain.Entity == ent]
        add(key, category="food", activity="Food product", subcategory=label, value=float(r["total"].iloc[0]), activity_unit="kg",
            geography="Global average", reporting_year="2010 (published 2018)", source_id="OWID_FOOD_SUPPLY_CHAIN", dataset_version="OWID-Poore2018",
            source_reference=f"OWID 'food-emissions-supply-chain', entity '{ent}' (sum of stages)", system_boundary=POORE_BOUNDARY,
            gases="CO2, CH4, N2O (CO2e, GWP100)", methodology=POORE_METH,
            derivation={"formula": "sum of supply-chain stage values", "stages": {s: round(float(r[s].iloc[0]), 4) for s in stages}}, dq=dq)
    # Tea - Premalatha et al. (2024) Plant Science Today 11(sp4), doi:10.14719/pst.5374 (Tamil Nadu black tea LCA)
    # Cradle-to-grave 12.9 kg CO2e/kg made tea, of which consumption stage 5.8 -> 7.1 excluding consumption,
    # aligning the boundary with Poore & Nemecek (which excludes consumer use).
    FACTORS.append({
        "factor_id": "food.tea@Premalatha2024", "factor_key": "food.tea", "category": "food", "activity": "Food product",
        "subcategory": "Black tea (made tea leaf)", "emission_factor": 7.1, "unit": "kg CO2e/kg", "activity_unit": "kg",
        "gas_basis": "CO2e", "geography": "India (Tamil Nadu)", "reporting_year": "2024",
        "source_id": "LIT_PREMALATHA_2024", "source_name": "Premalatha V. et al. (2024) 'Insights of carbon footprint of tea through life cycle approach', Plant Science Today 11(sp4)",
        "source_publisher": "Horizon e-Publishing Group", "source_url": "https://doi.org/10.14719/pst.5374",
        "source_landing_page": "https://horizonepublishing.com/journals/index.php/PST/article/view/5374",
        "source_reference": "Black tea cradle-to-grave 12.9 kg CO2e/kg made tea; consumption stage 5.8 kg CO2e/kg",
        "dataset_version": "Premalatha2024", "system_boundary": "Cultivation, processing, packaging, transport, disposal; consumption stage (boiling water, milk, sugar) REMOVED to align with farm-to-retail boundary.",
        "greenhouse_gases_included": "CO2e", "methodology": "Peer-reviewed attributional LCA, functional unit 1 kg made tea.",
        "derivation": {"formula": "12.9 - 5.8", "cradle_to_grave": 12.9, "consumption_stage": 5.8},
        "data_quality": quality(1, 1, 2, 3, "India-specific single-region study; literature value (not a downloadable dataset). Milk and sugar must be entered separately."),
        "uncertainty": "Single study; Indian tea LCAs report roughly 5-25 kg CO2e/kg depending on boundary.",
        "licence": "Cited literature value (fact) with attribution", "last_updated": TODAY, "is_active": True})

    # ---------------- meal models (NIN 'My Plate for the Day', 2024) ----------------
    nin_src = {"source_id": "NIN_MY_PLATE_2024", "name": "ICMR-National Institute of Nutrition, Policy Brief 'My Plate for the Day' (2024)",
               "url": "https://www.nin.res.in/brief/Policy%20Brief%20My%20Plate%20J18%2024.pdf",
               "local_path": "data/raw/food/NIN_Policy_Brief_My_Plate_2024.pdf"}
    daily = {"cereals": 250, "pulses": 85, "milk_curd": 300, "vegetables": 400, "fruits": 100, "nuts_seeds": 35, "fats_oils": 27}
    third = {k: v / 3 for k, v in daily.items()}
    fk = {f["factor_key"]: f for f in FACTORS if f["category"] == "food"}
    base = {"food.rice": third["cereals"] / 2, "food.wheat": third["cereals"] / 2, "food.pulses": third["pulses"],
            "food.milk": third["milk_curd"], "food.vegetables": third["vegetables"], "food.fruit": third["fruits"],
            "food.nuts": third["nuts_seeds"], "food.oil_palm": third["fats_oils"] / 2, "food.oil_soybean": third["fats_oils"] / 2}
    PROTEIN_PORTION_G = 100  # modelling assumption (raw weight) - see docs/methodology.md
    def meal(name, comp, notes):
        lines = [{"factor_key": k, "grams": round(g, 2), "factor": fk[k]["emission_factor"],
                  "kg_co2e": round(g / 1000 * fk[k]["emission_factor"], 5)} for k, g in comp.items()]
        return {"meal_type": name, "components": lines, "kg_co2e_per_meal": round(sum(l["kg_co2e"] for l in lines), 4), "notes": notes}
    models = []
    models.append(meal("vegetarian", base, "One-third of NIN 2000 kcal daily plate (raw weights). Cereals split 50/50 rice/wheat; oils 50/50 palm/soybean."))
    vegan = dict(base); vegan.pop("food.milk"); vegan["food.soy_milk"] = third["milk_curd"]
    models.append(meal("vegan", vegan, "Vegetarian model with dairy replaced 1:1 by soy milk."))
    for nm, key in [("non_vegetarian_chicken", "food.chicken"), ("non_vegetarian_fish", "food.fish_farmed"),
                    ("non_vegetarian_mutton", "food.mutton"), ("non_vegetarian_beef", "food.beef"), ("non_vegetarian_pork", "food.pork"),
                    ("non_vegetarian_egg", "food.eggs")]:
        comp = dict(base); comp.pop("food.pulses"); comp[key] = PROTEIN_PORTION_G
        models.append(meal(nm, comp, f"Vegetarian model with the pulse portion replaced by {PROTEIN_PORTION_G} g raw {fk[key]['subcategory'].lower()} "
                                     "(NIN: eggs/fish/meat can substitute a portion of pulses). Portion size is a MODELLING ASSUMPTION."))
    snack = {"food.milk": 100, "food.tea": 2, "food.sugar_cane": 5, "food.wheat": 30}
    models.append(meal("snack_refreshment", snack, "Tea with milk (100 ml milk, 2 g tea, 5 g sugar) + 30 g wheat-based snack. MODELLING ASSUMPTION."))
    coffee = {"food.milk": 100, "food.coffee": 7, "food.sugar_cane": 5, "food.wheat": 30}
    models.append(meal("snack_refreshment_coffee", coffee, "Coffee with milk (7 g coffee, 100 ml milk, 5 g sugar) + 30 g wheat snack. MODELLING ASSUMPTION."))
    (PROC / "meal_models.json").write_text(json.dumps({"basis": nin_src, "daily_plate_g": daily, "protein_portion_g": PROTEIN_PORTION_G,
                                                       "models": models}, indent=2))
    for m in models:
        FACTORS.append({
            "factor_id": f"food.meal.{m['meal_type']}@MealModel-2026.1", "factor_key": f"food.meal.{m['meal_type']}", "category": "food",
            "activity": "Meal (modelled)", "subcategory": m["meal_type"].replace("_", " ").title(), "emission_factor": m["kg_co2e_per_meal"],
            "unit": "kg CO2e/meal", "activity_unit": "meal", "gas_basis": "CO2e", "geography": "India diet composition x global food factors",
            "reporting_year": "2026 model", "source_id": "MEAL_MODEL", "source_name": "Modelled meal archetype: NIN 'My Plate for the Day' (2024) x Poore & Nemecek (2018)",
            "source_publisher": "This application (derived)", "source_url": nin_src["url"], "source_landing_page": "https://ourworldindata.org/environmental-impacts-of-food",
            "source_reference": "data/processed/meal_models.json", "dataset_version": "MealModel-2026.1", "system_boundary": POORE_BOUNDARY,
            "greenhouse_gases_included": "CO2e", "methodology": "Bottom-up: sum(component raw mass x Poore & Nemecek factor).",
            "derivation": {"formula": "sum(g/1000 x kgCO2e/kg)", "components": m["components"], "notes": m["notes"]},
            "data_quality": quality(2, 2, 4, 3, "Modelled composition - replace with ingredient-based entry when menu quantities are known."),
            "uncertainty": "High: depends on actual menu and portions.", "licence": "Derived (CC BY 4.0 inputs)", "last_updated": TODAY, "is_active": True})


# =========================================================================== AIRPORTS
def build_airports():
    df = pd.read_csv(RAW / "transportation" / "ourairports_airports.csv", low_memory=False)
    df = df[df.type.isin(["large_airport", "medium_airport"]) & df.iata_code.notna() & (df.iata_code.str.len() == 3)]
    keep = df[["iata_code", "name", "municipality", "iso_country", "latitude_deg", "longitude_deg", "type"]]
    keep = keep.sort_values(["type", "iata_code"]).drop_duplicates("iata_code")
    keep.to_csv(PROC / "transportation" / "airports.csv", index=False)
    return len(keep)


# =========================================================================== MAIN
def main():
    PROC.mkdir(parents=True, exist_ok=True)
    df26 = load_desnz("ghg-conversion-factors-2026-flat-format-revised.xlsx")
    df25 = load_desnz("ghg-conversion-factors-2025-flat-format.xlsx")
    build_desnz(df26, "DESNZ_2026_FLAT", "DESNZ-2026-v1.2", "2026", active=True)
    build_desnz(df25, "DESNZ_2025_FLAT", "DESNZ-2025", "2025", active=False)
    # cleaned DESNZ extract of the rows the app uses
    used_ids = {f["source_reference"].split("DESNZ ID ")[1].split()[0].rstrip(";") for f in FACTORS if "DESNZ ID" in f["source_reference"]}
    for cat in ["transportation", "accommodation", "materials", "waste"]:
        (PROC / cat).mkdir(parents=True, exist_ok=True)
    df26[df26.ID.isin(used_ids)].to_csv(PROC / "transportation" / "desnz_2026_rows_used.csv", index=False)
    ratio = build_cea()
    build_india_transport(df26)
    build_ev_factors(df26, "DESNZ-2026-v1.2")
    build_food()
    n_air = build_airports()

    # per-category processed CSVs
    flat = pd.json_normalize(FACTORS, sep=".")
    for cat, sub in flat.groupby("category"):
        d = PROC / (cat if cat in ("transportation", "accommodation", "food", "waste", "materials") else "electricity" if cat == "energy" else cat)
        d.mkdir(parents=True, exist_ok=True)
        sub.to_csv(d / f"{cat}_factors.csv", index=False)

    # uniqueness / sanity checks
    ids = [f["factor_id"] for f in FACTORS]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        raise SystemExit(f"Duplicate factor ids: {dup}")
    db = {"schema_version": "1.0", "factor_set_version": "FS-2026.1", "generated_at": TODAY,
          "gwp_basis": "IPCC AR5 GWP100 (CH4=28, N2O=265) unless noted", "factors": FACTORS}
    (PROC / "emission_factors.json").write_text(json.dumps(db, indent=2, default=str))
    flat.to_csv(PROC / "emission_factors.csv", index=False)

    versions = {}
    for f in FACTORS:
        v = versions.setdefault(f["dataset_version"], {"source_id": f["source_id"], "source_name": f["source_name"],
                                                       "reporting_year": f["reporting_year"], "factor_count": 0, "active": False})
        v["factor_count"] += 1
        v["active"] = v["active"] or f["is_active"]
    (META / "dataset_versions.json").write_text(json.dumps({"factor_set_version": "FS-2026.1", "generated_at": TODAY,
                                                            "dataset_versions": versions}, indent=2))
    dq_summary = {}
    for f in FACTORS:
        if not f["is_active"]:
            continue
        dq_summary.setdefault(f["category"], {"high": 0, "medium": 0, "low": 0})[f["data_quality"]["label"]] += 1
    (META / "data_quality.json").write_text(json.dumps({
        "method": "Pedigree-style 1-5 scores (geographical, temporal, technological, reliability); label high<=1.75<medium<=2.75<low",
        "summary_active_factors": dq_summary,
        "factors": {f["factor_id"]: f["data_quality"] for f in FACTORS}}, indent=2))
    print(f"Factors: {len(FACTORS)} ({sum(f['is_active'] for f in FACTORS)} active); airports: {n_air}; CEA CO2->CO2e ratio {ratio:.5f}")


if __name__ == "__main__":
    main()
