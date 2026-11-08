# Dataset Research and Acquisition Report

_Generated 2026-11-08 by `scripts/generate_acquisition_report.py` from `data/metadata/source_registry.json` and `data/processed/emission_factors.json` (factor set **FS-2026.1**, 416 records, 257 active)._

## 1. Summary

* **18 original files downloaded** from official/primary sources and stored unmodified in `data/raw/` with SHA-256 checksums.
* **1 download attempt failed** and is recorded below; 7 further datasets were researched but not acquired (registration, licence or paywall) - none were bypassed.
* India-specific factors were prioritised: CEA grid factor (FY 2025-26), India GHG Program road and rail factors, CHSB India hotel benchmark, Indian black-tea LCA and ICMR-NIN diet composition.
* Where no Indian factor exists, a documented international proxy is used and every affected calculation line is flagged `proxy`.
* `scripts/validate_datasets.py` re-verifies checksums, required metadata, one-active-factor-per-key, the CEA workbook ↔ user-guide cross-check and spot values against the original documents.

## 2. Successfully downloaded datasets

| Source id | Dataset | Format | Size | Version / year | Geography | Licence | Downloaded (UTC) | SHA-256 (first 12) |
|---|---|---|---|---|---|---|---|---|
| `CEA_BASELINE_V22_XLSX` | [CEA CO2 Baseline Database for the Indian Power Sector, Version 22.0 (database workbook)](https://cea.nic.in/api/cdm-report-version/view-pdf/en/83) | xlsx | 1.01 MB | 22.0 (August 2026, data for FY 2025-26) | India (national grid) | Government of India publication; publicly available for reference. Cited with attribution; no redistribution licence stated. | 2026-11-08T08:31:43 | `f2341efe03d2` |
| `CEA_BASELINE_V22_GUIDE` | [CEA CO2 Baseline Database User Guide, Version 22.0](https://cea.nic.in/api/cdm-report-version/view-pdf/en/82) | pdf | 0.84 MB | 22.0 (August 2026) | India | Government of India publication; publicly available for reference. | 2026-11-08T08:31:43 | `723331b2add3` |
| `CEA_BASELINE_V21_GUIDE` | [CEA CO2 Baseline Database User Guide, Version 21.0 (retained for version history)](https://cea.nic.in/api/cdm-report-version/view-pdf/en/78) | pdf | 0.80 MB | 21.0 (November 2025) | India | Government of India publication; publicly available for reference. | 2026-11-08T08:31:43 | `212a9f7d7a4c` |
| `CEA_BASELINE_V20_GUIDE` | [CEA CO2 Baseline Database User Guide, Version 20.0 (retained for version history)](https://cea.nic.in/api/cdm-report-version/view-pdf/en/76) | pdf | 1.17 MB | 20.0 (December 2024) | India | Government of India publication; publicly available for reference. | 2026-11-08T08:31:43 | `b881c258f58f` |
| `DESNZ_2026_FLAT` | [UK Government GHG Conversion Factors for Company Reporting 2026 - flat file (revised, v1.2)](https://assets.publishing.service.gov.uk/media/6a6c9748862aaf18d9c62ac9/ghg-conversion-factors-2026-flat-format-revised.xlsx) | xlsx | 0.52 MB | 2026 v1.2 | United Kingdom (international proxy where no Indian factor exists); hotel factors are country-specific | Open Government Licence v3.0 | 2026-11-08T08:30:49 | `a9a455ab396d` |
| `DESNZ_2026_FULL` | [UK Government GHG Conversion Factors 2026 - full set (human-readable workbook)](https://assets.publishing.service.gov.uk/media/6a29392bade52dc0882218a8/ghg-conversion-factors-2026-full-set.xlsx) | xlsx | 2.11 MB | 2026 | United Kingdom | Open Government Licence v3.0 | 2026-11-08T08:30:51 | `b5c4f2f86cdc` |
| `DESNZ_2026_METHODOLOGY` | [2026 GHG Conversion Factors Methodology Report](https://assets.publishing.service.gov.uk/media/6a2940543b15d05a7ce3202e/2026-GHG-conversion-factors-methodology-report.pdf) | pdf | 1.76 MB | 2026 | United Kingdom | Open Government Licence v3.0 | 2026-11-08T08:30:53 | `e15e575e3d54` |
| `DESNZ_2025_FLAT` | [UK Government GHG Conversion Factors 2025 - flat file (retained for version history)](https://assets.publishing.service.gov.uk/media/6846b6ea57f3515d9611f0dd/ghg-conversion-factors-2025-flat-format.xlsx) | xlsx | 0.51 MB | 2025 | United Kingdom | Open Government Licence v3.0 | 2026-11-08T08:30:53 | `8bfdb45b81ec` |
| `DESNZ_2025_METHODOLOGY` | [2025 GHG Conversion Factors Methodology Paper](https://assets.publishing.service.gov.uk/media/6846b0870392ed9b784c0187/2025-GHG-CF-methodology-paper.pdf) | pdf | 1.85 MB | 2025 | United Kingdom | Open Government Licence v3.0 | 2026-11-08T08:30:55 | `62774f77c18b` |
| `INDIAGHGP_ROAD_2015` | [India Specific Road Transport Emission Factors, Version 1.0 (2015)](https://indiaghgp.org/sites/default/files/Road%20Transport%20Technical%20Paper.pdf) | pdf | 4.93 MB | 1.0 (stakeholder consultation draft), 2015 | India | Copyright (c) 2015 India GHG Program, all rights reserved. Factor values cited with attribution; PDF kept locally for audit only, not redistributed. | 2026-11-08T08:33:05 | `82c52c2be634` |
| `INDIAGHGP_RAIL_2015` | [India Specific Rail Transport Emission Factors for Passenger Travel and Material Transport, Version 1.0 (2015)](https://indiaghgp.org/sites/default/files/Rail%20Transport%20Emission.pdf) | pdf | 2.49 MB | 1.0 (stakeholder consultation draft), 2015 | India | Copyright (c) 2015 India GHG Program, all rights reserved. Factor values cited with attribution; PDF kept locally for audit only. | 2026-11-08T08:33:06 | `7cc44c272a46` |
| `OURAIRPORTS` | [OurAirports airports database (airport coordinates for great-circle flight distances)](https://davidmegginson.github.io/ourairports-data/airports.csv) | csv | 12.76 MB | nightly snapshot | Global | Public Domain (Unlicense) | 2026-11-08T08:36:01 | `5754df21f25c` |
| `OWID_POORE_GHG_PER_KG` | [Greenhouse gas emissions per kilogram of food product (Poore & Nemecek 2018) - Our World in Data grapher export](https://ourworldindata.org/grapher/ghg-per-kg-poore.csv?v=1&csvType=full&useColumnShortNames=false) | csv | 0.8 kB | OWID export (data year 2010 global mean) | Global average | CC BY 4.0 | 2026-11-08T08:31:58 | `4c44efb5691f` |
| `OWID_POORE_GHG_PER_KG_META` | [Metadata for ghg-per-kg-poore](https://ourworldindata.org/grapher/ghg-per-kg-poore.metadata.json?v=1&csvType=full&useColumnShortNames=false) | json | 1.7 kB | OWID export | Global | CC BY 4.0 | 2026-11-08T08:31:59 | `c1f34b49c83d` |
| `OWID_FOOD_SUPPLY_CHAIN` | [Food emissions by supply-chain stage (Poore & Nemecek 2018) - Our World in Data grapher export](https://ourworldindata.org/grapher/food-emissions-supply-chain.csv?v=1&csvType=full&useColumnShortNames=false) | csv | 4.1 kB | OWID export | Global | CC BY 4.0 | 2026-11-08T08:32:01 | `6c3dba3f6147` |
| `NIN_MY_PLATE_2024` | [ICMR-NIN Policy Brief: My Plate for the Day (2024) - daily raw food quantities for a 2000 kcal Indian diet](https://www.nin.res.in/brief/Policy%20Brief%20My%20Plate%20J18%2024.pdf) | pdf | 0.67 MB | 2024 | India | Government of India (ICMR) public guidance; cited with attribution. | 2026-11-08T08:37:35 | `f7e6792056c9` |
| `EPA_WARM_V16` | [US EPA Waste Reduction Model (WARM) Version 16 (Excel)](https://www.epa.gov/system/files/documents/2023-12/warm_v16.xls) | xls | 3.61 MB | 16 (December 2023) | United States | US Government work (public domain) | 2026-11-08T08:36:03 | `5886bef67217` |
| `EPA_WARM_V16_GUIDE` | [WARM Version 16 Excel User's Guide (EPA 530-R-23-024)](https://www.epa.gov/system/files/documents/2023-12/warm-users-guide-excel_v16_dec.pdf) | pdf | 0.25 MB | 16 | United States | US Government work (public domain) | 2026-11-08T08:36:04 | `bb64822347aa` |

## 3. Datasets that could not be acquired

| Dataset | URL | Reason / substitute |
|---|---|---|
| Smart Freight Centre - India Default GHG Emission Values v1.2 | https://smart-freight-centre-media.s3.amazonaws.com/documents/India_Default_GHG_Emission_Values_SFC_INDIA_v1_2.pdf | Download failed: `HTTP Error 403: Forbidden`. Freight-only factors; would not be used for passenger travel. Listed so the acquisition attempt is recorded. Not required (freight-only). |
| Cornell Hotel Sustainability Benchmarking Index (CHSB) tool / HCMI | https://ecommons.cornell.edu/ and https://www.greenview.sg/services/chsb-index/ | Full CHSB tool requires registration/licence. Its 2021 country medians are republished in the DESNZ 2026 'Hotel stay' factors (methodology paper section 11), which are used instead. |
| ICE Database (Inventory of Carbon & Energy), Circular Ecology | https://circularecology.com/embodied-carbon-footprint-database.html | Download requires registration and acceptance of a licence. Not bypassed; DESNZ 'Material use' factors used instead. |
| EPD International / environdec.com product EPDs (banners, lanyards, bags) | https://www.environdec.com/library | Individual product EPDs are product- and manufacturer-specific and not suitable as generic defaults; no generic event-material EPDs found. DESNZ material factors used as documented proxies. |
| Poore & Nemecek (2018) full supplementary dataset (Science) | https://www.science.org/doi/10.1126/science.aaq0216 | Journal supplementary material behind publisher terms; the CC BY 4.0 Our World in Data republication of the same means is used. |
| Agribalyse 3.x (French food LCA database) | https://agribalyse.ademe.fr/ | Openly available but France-specific with a different (cradle-to-consumer) boundary; not mixed with Poore & Nemecek to avoid combining incompatible boundaries. |
| IEA emission factors database | https://www.iea.org/data-and-statistics/data-product/emissions-factors-2024 | Paid data product. CEA (official India source) used for India; DESNZ for the UK. |
| ICAO Carbon Emissions Calculator methodology data | https://www.icao.int/environmental-protection/CarbonOffset | Route-level calculator; underlying fuel-burn tables are not published as an open dataset. DESNZ aviation factors (EUROCONTROL-based) used instead. |

## 4. Dataset-by-dataset documentation

### 4.1 Electricity - CEA CO₂ Baseline Database for the Indian Power Sector (v22.0)

* **What:** station-level generation/emissions workbook (`Data`, `Results` sheets) and the User Guide v22.0 (August 2026, FY 2025-26); User Guides v21.0 and v20.0 kept for version history.
* **Where:** Central Electricity Authority, Ministry of Power - https://cea.nic.in/cdm-co2-baseline-database/?lang=en. The website's PDF links point to an API (`/api/cdm-report-version/view-pdf/en/<id>`); IDs 76, 78, 82 and 83 were identified as v20, v21, v22 guide and v22 workbook by reading each file's title page.
* **Extracted:** Annexure-I weighted average grid emission factor incl. renewables, captive and cross-border adjustment: **0.675 t CO₂/MWh (= kg CO₂/kWh) for FY 2025-26**; historical series FY 2016-17 → 2024-25 (`data/processed/electricity/india_grid_emission_factor_series_CEA_v22.csv`); FY 2025-26 generation mix from station data (`india_generation_mix_FY2025-26.csv`: coal ≈ 66%, non-hydro RE ≈ 18%, hydro ≈ 9%, nuclear ≈ 3%).
* **Cross-check:** workbook `Results` values agree with the user-guide Annexure-I within 0.001 for all years (cross-border adjusted from FY 2022-23, as the Annexure footnote states).
* **Units / gases:** t CO₂/MWh, CO₂ only. Converted to CO₂e with IPCC 2006 Vol. 2 Table 2.2 coal defaults (CH₄ 1, N₂O 1.5 kg/TJ; AR5 GWPs) → ratio 1.0045 → **0.6780 kg CO₂e/kWh**. Both records are stored.
* **Limitations:** generation-side factor, excludes T&D losses and upstream fuel; single national grid (no state factors published since grid integration); no residual-mix factor for market-based accounting.
* **Use:** venue electricity (location-based), hotel actual-energy method, Indian EV charging.

### 4.2 Transportation - UK DESNZ GHG Conversion Factors 2026 (and 2025)

* **What:** flat-format workbook v1.2 (machine-readable, 8,742 rows), full set and methodology paper; 2025 flat file and methodology retained.
* **Where:** https://www.gov.uk/government/publications/greenhouse-gas-reporting-conversion-factors-2026 (Open Government Licence v3.0).
* **Extracted (2026, kg CO₂e/passenger-km incl. RF):** short-haul economy 0.12576, long-haul (UK) economy 0.11704, long-haul business 0.33940, international non-UK economy 0.10916, first 0.43663; all classes with/without RF. Coach 0.03948, national rail 0.03092, international rail 0.01135, light rail 0.02121; cars by size × fuel (kg CO₂e/vehicle-km), taxis, motorbikes, EV kWh/km; fuels (diesel 2.66155 kg CO₂e/litre).
* **Boundary:** tank-to-wheel CO₂, CH₄, N₂O; aviation includes an 8% great-circle uplift; RF multiplier 1.7 on CO₂ in "with RF" factors; WTT excluded.
* **Limitations:** UK fleet/route mix; used as a proxy outside the UK and flagged.
* **Use:** flights (all), coach/intercity bus, international/metro rail, non-Indian road travel, stationary fuels, Indian EV energy use.

### 4.3 Transportation - India GHG Program (WRI India, CII, TERI), 2015

* **What:** *India Specific Road Transport Emission Factors* and *India Specific Rail Transport Emission Factors*, Version 1.0 (stakeholder consultation).
* **Where:** https://indiaghgp.org/ - PDFs only; tables extracted programmatically with `pdfplumber` (`india_ghgp_road_factors_extracted.csv`, `india_ghgp_rail_factors_extracted.json`).
* **Extracted:** 40 car segments, 8 two-wheeler, 3 three-wheeler factors (kg CO₂/km, with 10% real-world uplift), city bus 0.015161 kg CO₂/pkm; Indian Railways non-suburban 0.007837 and suburban 0.007976 kg CO₂/pkm (FY 2014-15).
* **Gas conversion:** published as CO₂ only → multiplied by the CH₄+N₂O share of the analogous DESNZ 2026 factor (e.g. India sedan diesel → 0.14239 kg CO₂e/vkm). Original and ratio stored in each record's `derivation`.
* **Limitations:** 2015 data; rail factor based on a pre-2015 grid factor (likely conservative); bus factor intracity only; no AC/sleeper class split; "all rights reserved" - values cited with attribution, PDFs not redistributed (git-ignored).

### 4.4 Accommodation - Cornell CHSB 2021 via DESNZ 2026 "Hotel stay"

* **What:** kg CO₂e per occupied room-night for 39 countries/cities - **India 58.9**, UK 10.4, USA 16.1, UAE 63.8.
* **Why via DESNZ:** the CHSB tool itself requires registration (not bypassed); DESNZ republishes the 2021 country medians (methodology section 11) under OGL.
* **Limitations:** median of participating (mostly branded) hotels, all classes combined - **no luxury/budget split is invented**; mixed AR4/AR5 GWP basis; 2021 data.

### 4.5 Food - Poore & Nemecek (2018) via Our World in Data

* **What:** kg CO₂e/kg product (global mean, 43 products) and the supply-chain stage breakdown (used for 5 vegetable oils); OWID metadata JSON.
* **Values (kg CO₂e/kg):** beef 99.48, mutton 39.72, cheese 23.88, fish (farmed) 13.63, pork 12.31, chicken 9.87, eggs 4.67, rice 4.45, milk 3.15, pulses 1.79, wheat 1.57, vegetables 0.53, coffee 28.53.
* **Tea:** not in Poore & Nemecek; Premalatha et al. (2024) *Plant Science Today* 11(sp4), doi:10.14719/pst.5374 (Tamil Nadu black tea): 12.9 kg CO₂e/kg cradle-to-grave minus 5.8 consumption stage = **7.1** (boundary aligned to farm-to-retail).
* **Meal models:** composition from the official ICMR-NIN *My Plate for the Day* (2024) table (250 g cereals, 85 g pulses, 300 ml milk, 400 g vegetables, 100 g fruit, 35 g nuts, 27 g oil per 2000 kcal); one main meal = ⅓ day → vegetarian 0.789, vegan 0.572, chicken 1.725, mutton 4.710 kg CO₂e/meal. The 100 g protein portion is a stated modelling assumption.
* **Boundary:** farm to retail incl. losses; excludes cooking and consumer waste - no other food dataset with a different boundary (e.g. Agribalyse) is mixed in.
* **Limitations:** global means; Indian rice paddy methane and dairy systems may differ. Licence CC BY 4.0.

### 4.6 Waste - DESNZ 2026 waste disposal (EPA WARM v16 kept for reference)

* **Values (kg CO₂e/kg):** food landfill 0.7003, food composting 0.0090, paper landfill 1.1645, mixed C&I landfill 0.5206, recycling / combustion 0.00465 (transport only).
* **Method:** GHG Protocol Scope 3 Category 5 *cut-off* approach; no recycling or energy-recovery credits.
* **WARM:** downloaded (US public domain) but not used for calculations because its life-cycle "avoided emissions" boundary is incompatible with the cut-off method.
* **Limitations:** UK landfill gas-capture assumptions likely **under-estimate** Indian landfill/dump-site methane; open burning not covered. Indian SWM publications provide waste composition, not disposal emission factors.

### 4.7 Materials - DESNZ 2026 material use

* **Values (kg CO₂e/kg, cradle-to-gate):** virgin paper 1.344, recycled paper 1.049, PVC 2.942 (banners, ID cards), PET 3.862 (bottles; polyester proxy), PP 2.575, textiles 22.310 (cotton bags, fabric banners), aluminium 9.114.
* **Derived:** printed pages → paper mass via ISO 216 sheet area × grammage; items → mass × factor; reusable items ÷ expected uses.
* **Not acquired:** ICE database (registration/licence), product EPDs (manufacturer-specific, not generic). Printing, sewing and dyeing energy excluded and disclosed.

### 4.8 Supporting data

* **OurAirports** (public domain): 4571 large/medium airports with IATA codes for offline great-circle flight distances.

## 5. Factor counts by source

| Source id | Factor records |
|---|---|
| `DESNZ_2026_FLAT` | 169 |
| `DESNZ_2025_FLAT` | 159 |
| `OWID_POORE_GHG_PER_KG` | 38 |
| `INDIAGHGP_ROAD_2015` | 17 |
| `CEA_BASELINE_V22_GUIDE` | 15 |
| `MEAL_MODEL` | 10 |
| `OWID_FOOD_SUPPLY_CHAIN` | 5 |
| `INDIAGHGP_RAIL_2015` | 2 |
| `LIT_PREMALATHA_2024` | 1 |

## 6. Reproducibility

```bash
python scripts/download_datasets.py      # downloads/verifies originals, writes source_registry.json
python scripts/process_datasets.py       # builds data/processed/*
python scripts/validate_datasets.py      # integrity & spot checks
python scripts/import_emission_factors.py  # loads factors into PostgreSQL
python scripts/generate_acquisition_report.py
```
