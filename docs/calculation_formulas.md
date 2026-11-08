# Calculation formulas

All results are in **kg CO₂e**; tonnes = kg ÷ 1,000. `legs` = 2 for return, 1 for one-way. Factor values below are the active values in factor set **FS-2026.1** (see `data/processed/emission_factors.json` for every factor's source and derivation).

## Transport

| Mode | Formula | Example factor |
|---|---|---|
| Flight | `passengers × GCD_km × legs × trips × EF_flight[band, class, RF]` | short-haul economy incl. RF: 0.12576 kg/pkm (DESNZ 2026) |
| Rail / bus (public) | `passengers × km × legs × trips × EF_pkm` | Indian Railways 0.00793 kg/pkm; India city bus 0.01527 |
| Car / taxi / two-wheeler / auto-rickshaw | `vehicles × km × legs × trips × EF_vkm`, with `vehicles = n_vehicles` if given, else `passengers ÷ occupancy` | India sedan diesel 0.14239 kg/vkm |
| Electric car (India) | `vehicles × km × legs × trips × (kWh/km × EF_grid_IN)` | 0.19422 kWh/km × 0.67804 = 0.13169 kg/vkm |
| Fuel-based (any vehicle) | `litres × EF_fuel` | diesel 2.66155 kg/L |
| Custom factor | `pkm (or vkm) × user factor` | — |

**Flight band:** within the UK → domestic; touches the UK → short-haul (≤ 3,700 km) / long-haul; otherwise short-haul (≤ 3,700 km) / international non-UK.
**Great-circle distance:** `GCD = 2R·asin(√(sin²(Δφ/2) + cosφ₁cosφ₂ sin²(Δλ/2)))`, with R = 6,371.0088 km.

## CO₂ → CO₂e conversions (documented derivations)

* **India road/rail (published as CO₂):** `EF_CO2e = EF_CO2 × (EF_total/EF_CO2)` of the analogous DESNZ 2026 factor (e.g. average diesel car ratio).
* **India grid (CEA, CO₂):** `EF_CO2e = EF_CO2 × (94600 + 1×28 + 1.5×265) / 94600 = 0.675 × 1.00450 = 0.67804`.

## Accommodation

`room_nights = rooms × nights` (or `guests ÷ guests_per_room × nights`, default 1 guest/room)
`E = room_nights × EF_country` (India 58.9 kg/room-night) | `room_nights × EF_hotel` | `kWh × EF_grid + Σ fuel × EF_fuel`

## Energy

* **Location-based:** `E_loc = grid_kWh × EF_grid` (India 0.67804)
* **Market-based:** `E_mkt = (grid_kWh − certified_renewable_kWh) × (EF_supplier or EF_grid)`
* **Estimated kWh (only if no meter):** `Σ power_kW × quantity × hours/day × days`
* **Fuels:** `litres (or kg, m³) × EF_fuel`, e.g. LPG `kg × 2939.36/1000`
* **Total reported (headline)** uses `E_loc`; `total_market = total − E_loc + E_mkt`.

## Food

* **Ingredients:** `kg × EF_food` (litres treated as kg at 1 kg/L).
* **Meals:** `count × EF_meal`, where `EF_meal = Σ_component (grams/1000 × EF_food)`.

Vegetarian meal = ⅓ × NIN daily plate (raw grams):

| Component | g | Factor (kg CO₂e/kg) | kg CO₂e |
|---|---|---|---|
| Rice | 41.67 | 4.45 | 0.1854 |
| Wheat | 41.67 | 1.57 | 0.0654 |
| Pulses | 28.33 | 1.79 | 0.0507 |
| Milk/curd | 100 | 3.15 | 0.3150 |
| Vegetables | 133.33 | 0.53 | 0.0707 |
| Fruit | 33.33 | 1.05 | 0.0350 |
| Nuts | 11.67 | 0.43 | 0.0050 |
| Palm oil | 4.5 | 7.317 (OWID stages sum) | 0.0329 |
| Soybean oil | 4.5 | 6.324 (OWID stages sum) | 0.0285 |
| **Total** | | | **0.7886** |

* **Bottled water:** `bottles × mass_g/1000 × EF_PET + bottles × L/1000 × EF_water_m3`

## Waste

`E = Σ_route kg_route × EF[material, route]`; `unassigned = generated − Σ routes → landfill (default)`; validation: `Σ routes ≤ generated`.

## Materials

* `kg = quantity` (kg, g, t converted) | `items × unit_mass_g / 1000` | `pages / (2 if duplex) × area_m² × gsm / 1000`
* **ISO 216 areas:** A3 0.12474 m², A4 0.06237 m², A5 0.03108 m².
* `E = kg × EF_material`, divided by `expected_uses` if reusable.

## Summary metrics

* `participants = attendees + speakers + organisers_staff + volunteers` (virtual excluded)
* `per_participant = total / participants`; `per_day = total / days`; `per_participant_day = total / participants / days`
* `share_c = 100 × E_c / total`
* `DQ score = Σ (E_line × pedigree_score_factor) / Σ E_line`
* `net_after_offsets = total_t − offsets_t` (gross is never reduced)

## Scenarios

`reduction = E_baseline − E_scenario` and `reduction_% = 100 × reduction / E_baseline` (both location- and market-based), with both runs on the same engine and factor set. Example from the specification (tested in `tests/test_scenarios.py`): 200 people × 30 km × 2 by individual petrol sedans (India) vs shared coaches:
`A = 12,000 vkm × 0.15365 = 1,843.8 kg`; `B = 12,000 pkm × 0.03948 = 473.8 kg` → reduction 1,370.0 kg (74%).
