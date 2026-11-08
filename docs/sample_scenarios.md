# Sample conference scenarios (SAMPLE DATA)

Three illustrative conferences live in `data/samples/*.json`. **They are not real events.** Their activity data is invented for testing and demonstration only. The emission factors applied to them are the real, documented factors.

Each total below was produced by an **independent line-by-line hand calculation** in `backend/tests/test_samples.py`. Every formula there is written out explicitly, and factor values are read from the factor database. The test asserts that the engine reproduces each total exactly. The test also asserts that the sample is complete and that no input entry appears in more than one category, which guards against double counting.

| Sample | Participants | Days | Total (kg CO₂e) | t CO₂e | kg per participant |
|---|---|---|---|---|---|
| Small academic, Bengaluru | 100 | 2 | **7,456.244** | 7.46 | 74.6 |
| Medium corporate, Mumbai | 500 | 2 | **111,783.290** | 111.78 | 223.6 |
| Large international, New Delhi (hybrid) | 2,000 | 4 | **1,511,540.428** | 1,511.54 | 755.8 |

Factor set FS-2026.1, with radiative forcing included.

## 1. Small academic workshop: 100 participants

| Line | Hand calculation | kg CO₂e |
|---|---|---|
| Speakers' flights DEL⇄BLR (economy, RF) | 10 × 1,700 km × 2 × 0.12576 | 4,275.84 |
| Train Chennai⇄Bengaluru | 30 × 350 × 2 × 0.00793 | 166.52 |
| City bus, daily | 40 × 15 × 2 × 2 × 0.01527 | 36.65 |
| Car-pool (petrol hatchback, 2 per car), daily | (10 ÷ 2) × 25 × 2 × 2 × 0.14059 | 70.30 |
| Guest house, India benchmark | 10 rooms × 2 nights × 58.9 | 1,178.00 |
| Grid electricity | 1,800 kWh × 0.67804 | 1,220.46 |
| Diesel generator | 40 L × 2.66155 | 106.46 |
| Meals | 150 × 0.7886 + 50 × 1.7249 + 400 × 0.3923 | 361.45 |
| Bottled water (sample bottle mass 10 g) | 2 kg PET × 3.8616 + 0.1 m³ × 0.1913 | 7.74 |
| Waste | 25 kg compost, 15 kg food landfill, 10 kg paper recycling, 5 kg paper landfill, 8 kg plastic landfill | 16.67 |
| Materials | 800 duplex A4 pages at 80 gsm (2.00 kg) × 1.3436 + 3 kg PVC × 2.9424 + 1.2 kg PET × 3.8616 | 16.14 |
| **Total** | | **7,456.24** |

Shares: transportation 61.0%, energy 17.8%, accommodation 15.8%, food 5.0%, waste 0.2%, materials 0.2%.

## 2. Medium corporate summit: 500 participants

Flight distances are great-circle distances from airport coordinates:

| Line | kg CO₂e |
|---|---|
| 120 × DEL⇄BOM (short-haul economy) | 34,311.85 |
| 80 × BLR⇄BOM | 16,784.71 |
| 5 × SIN⇄BOM business (international non-UK, more than 3,700 km) | 12,414.92 |
| 4 × LHR⇄BOM economy (long-haul, UK) | 6,753.59 |
| Train Pune (60 × 190 km × 2) | 180.79 |
| Suburban rail (100 × 20 km × 2 × 2) | 64.56 |
| CNG taxis (209 ÷ 1.5 × 18 km × 2) | 345.34 |
| Diesel SUVs (80 ÷ 1.2 × 22 km × 2 × 2) | 1,244.11 |
| Hotel, 230 rooms × 2 nights × 58.9 | 27,094.00 |
| Energy: 9,500 kWh, 150 L diesel, 120 kg LPG | 7,193.30 |
| Meals (1,260 vegetarian, 350 chicken, 100 fish, 200 mutton, 2,000 coffee + snack) | 3,905.02 |
| Bottled water | 58.07 |
| Waste | 215.50 |
| Materials | 1,217.54 |
| **Total** | **111,783.29** |

## 3. Large international congress: 2,000 participants (hybrid, offsets)

| Line | kg CO₂e |
|---|---|
| International flights: LHR 236,356 · JFK 307,972 · SIN 90,803 · DXB 43,909 · NRT 77,419 · FRA business 155,034 | 911,492.77 |
| Domestic flights: BOM 85,780 · BLR 107,454 · CCU 49,534 | 242,768.01 |
| Train 1,903 · metro 1,629 · coaches 3,316 · taxis 1,721 · EVs 421 | 8,990.86 |
| Hotels: 1,100 rooms × 4 × 58.9, plus 100 × 4 × 25.0 (sample hotel-supplied factor) | 269,160.00 |
| Energy: 64,000 kWh, 1,500 L diesel, 900 kg LPG | 50,032.06 |
| Meals | 22,761.05 |
| Waste | 1,225.88 |
| Materials | 5,109.79 |
| **Total (gross)** | **1,511,540.43** |

Other reported figures for this sample:

* **Market-based total:** 1,498.52 t. 19,200 kWh are covered by certificates, and 6,000 kWh of on-site solar counts as zero in both methods.
* **Offsets:** 100 t (sample), reported separately. Gross minus offsets is 1,411.54 t.

## Regenerating the reference totals

```bash
cd backend && ../.venv/bin/python -m pytest tests/test_samples.py -v
```

If a factor is updated, the hand-calculation test still passes, because it reads the new factor values. The `REFERENCE_TOTALS` regression assertion fails deliberately, so the documented totals must be reviewed and updated together with the factor set version.
