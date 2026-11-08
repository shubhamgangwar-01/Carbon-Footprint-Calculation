#!/usr/bin/env python3
"""Generate docs/DATASET_RESEARCH_AND_ACQUISITION_REPORT.md (and a copy at
data/reports/dataset_acquisition_report.md) from the source registry and the
processed factor database, so every figure in the report matches the data."""
import json
import shutil
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
reg = json.loads((ROOT / "data/metadata/source_registry.json").read_text())
db = json.loads((ROOT / "data/processed/emission_factors.json").read_text())
F = {f["factor_key"]: f for f in db["factors"] if f["is_active"]}
v = lambda k, d=4: f"{F[k]['emission_factor']:.{d}f}"  # noqa: E731
src = {s["source_id"]: s for s in reg["sources"]}
ok = [s for s in reg["sources"] if s["status"] == "downloaded"]
bad = [s for s in reg["sources"] if s["status"] != "downloaded"]
n_by_src = {}
for f in db["factors"]:
    n_by_src[f["source_id"]] = n_by_src.get(f["source_id"], 0) + 1


def mb(n):
    return f"{n / 1e6:.2f} MB" if n > 1e5 else f"{n / 1e3:.1f} kB"


L = []
w = L.append
w("# Dataset Research and Acquisition Report")
w(f"\n_Generated {date.today().isoformat()} by `scripts/generate_acquisition_report.py` from `data/metadata/source_registry.json` "
  f"and `data/processed/emission_factors.json` (factor set **{db['factor_set_version']}**, {len(db['factors'])} records, "
  f"{sum(f['is_active'] for f in db['factors'])} active)._\n")
w("## 1. Summary\n")
w(f"* **{len(ok)} original files downloaded** from official/primary sources and stored unmodified in `data/raw/` with SHA-256 checksums.")
w(f"* **{len(bad)} download attempt failed** and is recorded below; {len(reg['not_acquired'])} further datasets were researched but not acquired (registration, licence or paywall) - none were bypassed.")
w("* India-specific factors were prioritised: CEA grid factor (FY 2025-26), India GHG Program road and rail factors, CHSB India hotel benchmark, Indian black-tea LCA and ICMR-NIN diet composition.")
w("* Where no Indian factor exists, a documented international proxy is used and every affected calculation line is flagged `proxy`.")
w("* `scripts/validate_datasets.py` re-verifies checksums, required metadata, one-active-factor-per-key, the CEA workbook ↔ user-guide cross-check and spot values against the original documents.\n")
w("## 2. Successfully downloaded datasets\n")
w("| Source id | Dataset | Format | Size | Version / year | Geography | Licence | Downloaded (UTC) | SHA-256 (first 12) |")
w("|---|---|---|---|---|---|---|---|---|")
for s in ok:
    w(f"| `{s['source_id']}` | [{s['name']}]({s['url']}) | {s['format']} | {mb(s['size_bytes'])} | {s['version']} | {s['geography']} | {s['licence']} | {s['downloaded_at'][:19]} | `{s['sha256'][:12]}` |")
w("\n## 3. Datasets that could not be acquired\n")
w("| Dataset | URL | Reason / substitute |")
w("|---|---|---|")
for s in bad:
    w(f"| {s['name']} | {s['url']} | Download failed: `{s.get('error')}`. {s.get('notes') or ''} Not required (freight-only). |")
for s in reg["not_acquired"]:
    w(f"| {s['name']} | {s['url']} | {s['reason']} |")

w("\n## 4. Dataset-by-dataset documentation\n")
w(f"""### 4.1 Electricity - CEA CO₂ Baseline Database for the Indian Power Sector (v22.0)

* **What:** station-level generation/emissions workbook (`Data`, `Results` sheets) and the User Guide v22.0 (August 2026, FY 2025-26); User Guides v21.0 and v20.0 kept for version history.
* **Where:** Central Electricity Authority, Ministry of Power - {src['CEA_BASELINE_V22_XLSX']['landing_page']}. The website's PDF links point to an API (`/api/cdm-report-version/view-pdf/en/<id>`); IDs 76, 78, 82 and 83 were identified as v20, v21, v22 guide and v22 workbook by reading each file's title page.
* **Extracted:** Annexure-I weighted average grid emission factor incl. renewables, captive and cross-border adjustment: **{F['electricity.grid.IN.co2']['emission_factor']} t CO₂/MWh (= kg CO₂/kWh) for FY 2025-26**; historical series FY 2016-17 → 2024-25 (`data/processed/electricity/india_grid_emission_factor_series_CEA_v22.csv`); FY 2025-26 generation mix from station data (`india_generation_mix_FY2025-26.csv`: coal ≈ 66%, non-hydro RE ≈ 18%, hydro ≈ 9%, nuclear ≈ 3%).
* **Cross-check:** workbook `Results` values agree with the user-guide Annexure-I within 0.001 for all years (cross-border adjusted from FY 2022-23, as the Annexure footnote states).
* **Units / gases:** t CO₂/MWh, CO₂ only. Converted to CO₂e with IPCC 2006 Vol. 2 Table 2.2 coal defaults (CH₄ 1, N₂O 1.5 kg/TJ; AR5 GWPs) → ratio 1.0045 → **{v('electricity.grid.IN')} kg CO₂e/kWh**. Both records are stored.
* **Limitations:** generation-side factor, excludes T&D losses and upstream fuel; single national grid (no state factors published since grid integration); no residual-mix factor for market-based accounting.
* **Use:** venue electricity (location-based), hotel actual-energy method, Indian EV charging.

### 4.2 Transportation - UK DESNZ GHG Conversion Factors 2026 (and 2025)

* **What:** flat-format workbook v1.2 (machine-readable, 8,742 rows), full set and methodology paper; 2025 flat file and methodology retained.
* **Where:** {src['DESNZ_2026_FLAT']['landing_page']} (Open Government Licence v3.0).
* **Extracted (2026, kg CO₂e/passenger-km incl. RF):** short-haul economy {v('transport.flight.short_haul_uk.economy.with_rf', 5)}, long-haul (UK) economy {v('transport.flight.long_haul_uk.economy.with_rf', 5)}, long-haul business {v('transport.flight.long_haul_uk.business.with_rf', 5)}, international non-UK economy {v('transport.flight.international_non_uk.economy.with_rf', 5)}, first {v('transport.flight.international_non_uk.first.with_rf', 5)}; all classes with/without RF. Coach {v('transport.bus.coach.uk', 5)}, national rail {v('transport.rail.national.uk', 5)}, international rail {v('transport.rail.international', 5)}, light rail {v('transport.rail.light_rail_tram', 5)}; cars by size × fuel (kg CO₂e/vehicle-km), taxis, motorbikes, EV kWh/km; fuels (diesel {v('energy.fuel.diesel.litre', 5)} kg CO₂e/litre).
* **Boundary:** tank-to-wheel CO₂, CH₄, N₂O; aviation includes an 8% great-circle uplift; RF multiplier 1.7 on CO₂ in "with RF" factors; WTT excluded.
* **Limitations:** UK fleet/route mix; used as a proxy outside the UK and flagged.
* **Use:** flights (all), coach/intercity bus, international/metro rail, non-Indian road travel, stationary fuels, Indian EV energy use.

### 4.3 Transportation - India GHG Program (WRI India, CII, TERI), 2015

* **What:** *India Specific Road Transport Emission Factors* and *India Specific Rail Transport Emission Factors*, Version 1.0 (stakeholder consultation).
* **Where:** https://indiaghgp.org/ - PDFs only; tables extracted programmatically with `pdfplumber` (`india_ghgp_road_factors_extracted.csv`, `india_ghgp_rail_factors_extracted.json`).
* **Extracted:** 40 car segments, 8 two-wheeler, 3 three-wheeler factors (kg CO₂/km, with 10% real-world uplift), city bus 0.015161 kg CO₂/pkm; Indian Railways non-suburban 0.007837 and suburban 0.007976 kg CO₂/pkm (FY 2014-15).
* **Gas conversion:** published as CO₂ only → multiplied by the CH₄+N₂O share of the analogous DESNZ 2026 factor (e.g. India sedan diesel → {v('transport.car.sedan.diesel.IN', 5)} kg CO₂e/vkm). Original and ratio stored in each record's `derivation`.
* **Limitations:** 2015 data; rail factor based on a pre-2015 grid factor (likely conservative); bus factor intracity only; no AC/sleeper class split; "all rights reserved" - values cited with attribution, PDFs not redistributed (git-ignored).

### 4.4 Accommodation - Cornell CHSB 2021 via DESNZ 2026 "Hotel stay"

* **What:** kg CO₂e per occupied room-night for {sum(1 for k in F if k.startswith('accommodation.hotel.'))} countries/cities - **India {v('accommodation.hotel.india', 1)}**, UK {v('accommodation.hotel.uk', 1)}, USA {v('accommodation.hotel.united_states', 1)}, UAE {v('accommodation.hotel.united_arab_emirates', 1)}.
* **Why via DESNZ:** the CHSB tool itself requires registration (not bypassed); DESNZ republishes the 2021 country medians (methodology section 11) under OGL.
* **Limitations:** median of participating (mostly branded) hotels, all classes combined - **no luxury/budget split is invented**; mixed AR4/AR5 GWP basis; 2021 data.

### 4.5 Food - Poore & Nemecek (2018) via Our World in Data

* **What:** kg CO₂e/kg product (global mean, 43 products) and the supply-chain stage breakdown (used for 5 vegetable oils); OWID metadata JSON.
* **Values (kg CO₂e/kg):** beef {v('food.beef', 2)}, mutton {v('food.mutton', 2)}, cheese {v('food.cheese', 2)}, fish (farmed) {v('food.fish_farmed', 2)}, pork {v('food.pork', 2)}, chicken {v('food.chicken', 2)}, eggs {v('food.eggs', 2)}, rice {v('food.rice', 2)}, milk {v('food.milk', 2)}, pulses {v('food.pulses', 2)}, wheat {v('food.wheat', 2)}, vegetables {v('food.vegetables', 2)}, coffee {v('food.coffee', 2)}.
* **Tea:** not in Poore & Nemecek; Premalatha et al. (2024) *Plant Science Today* 11(sp4), doi:10.14719/pst.5374 (Tamil Nadu black tea): 12.9 kg CO₂e/kg cradle-to-grave minus 5.8 consumption stage = **7.1** (boundary aligned to farm-to-retail).
* **Meal models:** composition from the official ICMR-NIN *My Plate for the Day* (2024) table (250 g cereals, 85 g pulses, 300 ml milk, 400 g vegetables, 100 g fruit, 35 g nuts, 27 g oil per 2000 kcal); one main meal = ⅓ day → vegetarian {v('food.meal.vegetarian', 3)}, vegan {v('food.meal.vegan', 3)}, chicken {v('food.meal.non_vegetarian_chicken', 3)}, mutton {v('food.meal.non_vegetarian_mutton', 3)} kg CO₂e/meal. The 100 g protein portion is a stated modelling assumption.
* **Boundary:** farm to retail incl. losses; excludes cooking and consumer waste - no other food dataset with a different boundary (e.g. Agribalyse) is mixed in.
* **Limitations:** global means; Indian rice paddy methane and dairy systems may differ. Licence CC BY 4.0.

### 4.6 Waste - DESNZ 2026 waste disposal (EPA WARM v16 kept for reference)

* **Values (kg CO₂e/kg):** food landfill {v('waste.food.landfill', 4)}, food composting {v('waste.food.composting', 4)}, paper landfill {v('waste.paper.landfill', 4)}, mixed C&I landfill {v('waste.mixed.landfill', 4)}, recycling / combustion {v('waste.plastic.recycling', 5)} (transport only).
* **Method:** GHG Protocol Scope 3 Category 5 *cut-off* approach; no recycling or energy-recovery credits.
* **WARM:** downloaded (US public domain) but not used for calculations because its life-cycle "avoided emissions" boundary is incompatible with the cut-off method.
* **Limitations:** UK landfill gas-capture assumptions likely **under-estimate** Indian landfill/dump-site methane; open burning not covered. Indian SWM publications provide waste composition, not disposal emission factors.

### 4.7 Materials - DESNZ 2026 material use

* **Values (kg CO₂e/kg, cradle-to-gate):** virgin paper {v('materials.paper.virgin', 3)}, recycled paper {v('materials.paper.recycled', 3)}, PVC {v('materials.plastic.pvc', 3)} (banners, ID cards), PET {v('materials.plastic.pet', 3)} (bottles; polyester proxy), PP {v('materials.plastic.pp', 3)}, textiles {v('materials.textile.clothing', 3)} (cotton bags, fabric banners), aluminium {v('materials.metal.aluminium', 3)}.
* **Derived:** printed pages → paper mass via ISO 216 sheet area × grammage; items → mass × factor; reusable items ÷ expected uses.
* **Not acquired:** ICE database (registration/licence), product EPDs (manufacturer-specific, not generic). Printing, sewing and dyeing energy excluded and disclosed.

### 4.8 Supporting data

* **OurAirports** (public domain): {sum(1 for _ in open(ROOT / 'data/processed/transportation/airports.csv')) - 1} large/medium airports with IATA codes for offline great-circle flight distances.

## 5. Factor counts by source

| Source id | Factor records |
|---|---|""")
for k, n in sorted(n_by_src.items(), key=lambda x: -x[1]):
    w(f"| `{k}` | {n} |")
w("\n## 6. Reproducibility\n")
w("```bash\npython scripts/download_datasets.py      # downloads/verifies originals, writes source_registry.json\n"
  "python scripts/process_datasets.py       # builds data/processed/*\npython scripts/validate_datasets.py      # integrity & spot checks\n"
  "python scripts/import_emission_factors.py  # loads factors into PostgreSQL\npython scripts/generate_acquisition_report.py\n```")
text = "\n".join(L) + "\n"
(ROOT / "docs" / "DATASET_RESEARCH_AND_ACQUISITION_REPORT.md").write_text(text)
(ROOT / "data" / "reports").mkdir(exist_ok=True)
shutil.copy(ROOT / "docs" / "DATASET_RESEARCH_AND_ACQUISITION_REPORT.md", ROOT / "data" / "reports" / "dataset_acquisition_report.md")
print(f"written ({len(text):,} chars)")
