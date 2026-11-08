# Methodology

## 1. Standards and principles

The calculator follows:

* **GHG Protocol Corporate Accounting and Reporting Standard.** It uses the operational-control logic, applied to an event boundary.
* **GHG Protocol Scope 2 Guidance.** Electricity is dual-reported, location-based and market-based.
* **GHG Protocol Corporate Value Chain (Scope 3) Standard**, for the categories relevant to an event organiser:
  * Cat. 1: purchased goods (catering, materials)
  * Cat. 5: waste generated in operations
  * Cat. 6: business travel (staff and speakers)
  * Cat. 7: attendee travel, treated by analogy
* **ISO 14064-1:2018 principles:** relevance, completeness, consistency, accuracy and transparency, with conservativeness where an assumption is needed.

The core rule for every activity is:

```
emissions (kg CO2e) = activity quantity (in the factor's activity unit) × emission factor (kg CO2e / unit)
total = Σ activities;   tonnes = kg / 1000
```

GWP basis: IPCC AR5 100-year (CO₂ = 1, CH₄ = 28, N₂O = 265), the same basis as DESNZ 2026.

## 2. Boundary

| Included | Scope (organiser view) | Excluded (disclosed) |
|---|---|---|
| Delegate, speaker and staff travel to/from the event and local commutes | Scope 3 Cat. 6/7 | Well-to-tank fuel supply, vehicle manufacture |
| Accommodation (hotel operational energy per occupied room-night) | Scope 3 Cat. 6 | Hotel food/laundry, embodied emissions |
| Venue electricity and fuels (generators, LPG, gas) | Scope 2 / Scope 1 | T&D losses, upstream electricity |
| Catering (food production farm-to-retail), bottled water | Scope 3 Cat. 1 | Consumer cooking beyond venue energy data, consumer waste |
| Waste by material and disposal route | Scope 3 Cat. 5 | Biogenic CO₂, open burning |
| Purchased event materials (cradle-to-gate) | Scope 3 Cat. 1 | Printing energy/ink, sewing/dyeing, capital goods |
| — | — | Virtual participation (devices, networks, data centres) |

## 3. Data hierarchy and India-first factor selection

For each activity the engine picks the most specific documented factor:

1. **Actual / supplier-specific data.** Examples: metered kWh, fuel litres, a hotel's own kg CO₂e per room-night, a transport operator's factor.
2. **India-specific published factors:**
   * CEA grid factor v22.0 (FY 2025-26)
   * India GHG Program road and rail factors (2015)
   * CHSB India hotel benchmark
   * Indian black-tea LCA
   * ICMR-NIN diet composition
3. **Documented international proxies** (DESNZ 2026, Poore & Nemecek global means). Every line using a proxy is flagged `proxy`, and the share of emissions from proxies is reported.

## 4. Activity data types

Each entry is tagged with one of three activity-data types, and the dashboard and report show emissions by type:

* **actual:** measured data or records.
* **estimated:** for example, flight distance derived from airport coordinates, electricity estimated from rated loads, or an optional geocoded distance.
* **default:** a conservative assumption applied by the engine because an input was missing, such as occupancy 1, 1 guest per room, petrol fuel, or unassigned waste going to landfill.

## 5. Missing data, completeness and double counting

* A module with **no data is reported as "not reported"** and is never treated as zero. A module explicitly declared **not applicable** is reported as zero with that declaration recorded.
* An entry that cannot be calculated (missing distance, missing bottle mass, a country with no grid factor) produces an **error issue**. The entry is not counted and its category is marked **incomplete**.
* **No double counting:**
  * **Electricity:** a metered reading suppresses all load-based estimates.
  * **Food:** meal-based and ingredient-based methods are mutually exclusive per meal service (enforced by validation).
  * **Food waste:** entered on the Food page, it is the same record as on the Waste page and counted once.
  * **Vehicle modes:** counted per vehicle-km and shared by occupants. Public modes are counted per passenger-km.
  * **Waste routes:** the total routed cannot exceed the waste generated (validation).
  * **Fuel-based entries:** a transport entry with actual fuel litres ignores its distance inputs.

## 6. Data quality and uncertainty

Every factor carries a pedigree-style score from 1 (best) to 5 (worst), after Weidema & Wesnaes (1996), as used by ecoinvent and in GHG Protocol Scope 3 Standard chapter 7. It combines four indicators:

* geographical representativeness
* temporal representativeness
* technological representativeness
* source reliability

The result shows:

* the **emissions-weighted factor quality score** and label (high ≤ 1.75 < medium ≤ 2.75 < low)
* the share of emissions from actual, estimated and default activity data
* the share of emissions calculated with proxy factors
* a qualitative uncertainty rating

Most sources do not publish statistical uncertainty ranges, so **no numerical confidence interval is claimed**.

## 7. Electricity (Scope 2)

* **Location-based (headline):** grid kWh × grid factor. India: CEA v22.0 Annexure-I weighted average incl. renewables, captive and cross-border adjustment, 0.675 kg CO₂/kWh.
  * This is converted to CO₂e with IPCC 2006 default CH₄/N₂O for coal combustion (×1.0045), giving **0.678 kg CO₂e/kWh**.
  * Historical CEA years can be selected to reproduce past events.
* **Market-based:** kWh covered by renewable certificates or a green tariff count as zero. The remainder uses the grid average, because no Indian residual-mix factor is published (disclosed). A supplier-specific factor can be entered.
* **On-site renewables** consumed directly count as zero in both methods.

## 8. Transport

* **Flights:** passenger-km × DESNZ 2026 factor by band and cabin class.
  * Distances are great-circle distances, from airport coordinates if not entered. The DESNZ factors already include an 8% routing uplift.
  * Radiative forcing (×1.7 on CO₂) is on by default and can be switched off.
  * **Bands:**
    * Flights within the UK use the UK-domestic factor.
    * Other flights touching the UK: short-haul up to 3,700 km, long-haul (UK) above.
    * Flights not touching the UK: DESNZ short-haul up to 3,700 km, DESNZ "International, to/from non-UK" above.
  * The 3,700 km split follows the crude rule described in DESNZ methodology §8.8.
  * Short-haul premium economy and first class map to business class (conservative).
* **Rail in India:** India GHG Program non-suburban or suburban factors.
  * **Metro:** the DESNZ light-rail proxy, because the India GHG Program factors exclude MRTS.
  * **International rail:** DESNZ.
* **Bus:**
  * India intracity: India GHG Program factor.
  * Coach, intercity and chartered shuttles: DESNZ coach proxy.
* **Car, taxi, two-wheeler, auto-rickshaw:** vehicle-km = (passengers ÷ occupancy, or the number of vehicles) × distance × legs × trips.
  * India factors are the India GHG Program values with the 10% real-world uplift, converted to CO₂e.
  * Indian EVs: DESNZ real-world kWh/km × CEA grid factor.
  * Elsewhere: DESNZ factors by size and fuel.

## 9. Accommodation

Three methods, in order of priority:

1. Actual hotel energy: kWh × grid factor, plus fuels.
2. A hotel-supplied factor × room-nights.
3. The CHSB 2021 country median (via DESNZ) × room-nights. Room-nights = rooms × nights. If rooms are unknown, guests ÷ guests per room is used, defaulting to 1 guest per room.

No hotel-class factors are invented.

## 10. Food and beverages

* **Ingredient method:** kg × Poore & Nemecek (2018) global mean factor (farm to retail, including supply-chain losses).
* **Meal method:** count × modelled per-meal factor.
  * One main meal = ⅓ of the ICMR-NIN *My Plate for the Day* (2024) 2000 kcal plate, in raw weights:
    * cereals: 50/50 rice and wheat
    * pulses
    * milk/curd
    * vegetables
    * fruit
    * nuts
    * oils: 50/50 palm and soybean
  * **Vegan:** dairy is replaced by soy milk.
  * **Non-vegetarian:** the pulse portion is replaced by 100 g raw meat, fish or egg. This portion size is a stated assumption.
  * **Snacks:** tea or coffee with milk and sugar, plus a 30 g wheat snack (assumption).
* **Tea:** Premalatha et al. (2024), Tamil Nadu black tea, consumption stage removed: 7.1 kg CO₂e/kg.
* **Bottled water:** PET mass (user-supplied, required) × the DESNZ PET factor, plus the water volume × the DESNZ water-supply proxy.

## 11. Waste

kg × DESNZ 2026 disposal factor, using the cut-off method:

* Recycling, composting, AD and combustion carry collection and transport only.
* Landfill includes decomposition methane, under UK gas-capture assumptions. This is **likely an under-estimate for India**.
* Waste not assigned to a route goes to landfill as a flagged default.
* No avoided-emission credits are claimed.

## 12. Materials

kg × DESNZ 2026 cradle-to-gate material factor:

* **Pages → kg:** pages (÷ 2 if double-sided) × ISO 216 sheet area × grammage.
* **Items → kg:** count × mass per item (required).
* **Reusable items:** emissions ÷ expected uses (a user assumption, default 5).

## 13. Offsets

Offsets are entered and reported separately. Gross emissions are never reduced. "Gross minus offsets" is shown for information only.

## 14. Reproducibility

* Each factor has an immutable id `factor_key@dataset_version`.
* Every calculation stores:
  * its input snapshot
  * every line with its factor id and value
  * the list of factors used
  * the factor-set and engine versions
* `GET /api/calculations/{id}/verify` recomputes with the pinned factor ids and confirms an identical total, even after administrators publish new factor versions.
* PDF reports are rendered only from stored calculations and saved with a SHA-256 checksum.
