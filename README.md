---
title: Conference Carbon API
emoji: 🌍
colorFrom: green
colorTo: blue
sdk: gradio
app_file: app.py
pinned: false
---

# Conference Carbon Footprint Calculator

A full-stack web application that calculates, analyses and helps reduce the greenhouse-gas emissions of a conference.

Organisers enter details over a 7-step form:

* travel
* accommodation
* venue energy
* catering
* waste
* materials

The application returns:

* a transparent footprint in kg and t CO₂e (total, per participant, per day, by category and by activity)
* data-quality and actual-versus-estimated indicators
* what-if scenarios and results-driven recommendations
* a professional PDF report

**Scientific basis.** Every emission factor comes from a downloaded, checksummed official or peer-reviewed dataset, and India-specific data is used first:

* **CEA CO₂ Baseline Database v22.0 (FY 2025-26):** Indian grid factor of 0.675 kg CO₂/kWh, or 0.678 kg CO₂e/kWh.
* **India GHG Program:** road and rail factors.
* **Cornell CHSB:** India hotel benchmark of 58.9 kg CO₂e per room-night.
* **UK DESNZ 2026:** aviation and international proxies.
* **Poore & Nemecek (2018):** food life-cycle data.
* **ICMR-NIN *My Plate* (2024):** Indian meal composition.

Calculations follow the GHG Protocol and ISO 14064-1 principles.

---

## Quick start (local)

**Prerequisites:** Python 3.12, Node 20, and PostgreSQL 16 or 17 running locally. Docker is an alternative; see below.

```bash
# 1. Python environment
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt

# 2. Configuration
cp .env.example .env            # set SECRET_KEY, ADMIN_EMAIL, ADMIN_PASSWORD
createdb conference_carbon

# 3. Data pipeline (already run - outputs are committed in data/processed; re-run to refresh)
.venv/bin/python scripts/download_datasets.py
.venv/bin/python scripts/process_datasets.py
.venv/bin/python scripts/validate_datasets.py

# 4. Database schema + factors
cd backend && ../.venv/bin/alembic upgrade head && cd ..
.venv/bin/python scripts/import_emission_factors.py

# 5. Run
cd backend && ../.venv/bin/uvicorn app.main:app --port 8000      # API  → http://localhost:8000/docs
cd frontend && npm install && npm run dev                         # UI   → http://localhost:5173
```

On startup the API applies migrations (`AUTO_MIGRATE=true`), seeds the factor table if it is empty, and creates the admin user from `ADMIN_EMAIL` / `ADMIN_PASSWORD`. Visitors get a guest session automatically. Signing in with the admin account unlocks `/admin`.

### Docker

```bash
echo "SECRET_KEY=$(python3 -c 'import secrets;print(secrets.token_hex(32))')" >> .env
docker compose up --build        # UI http://localhost:8080 · API http://localhost:8000
```

## Tests

```bash
cd backend && ../.venv/bin/python -m pytest -q          # 80 tests
../.venv/bin/python ../scripts/validate_datasets.py     # dataset integrity
cd ../frontend && npx tsc -b && ../.venv/bin/python e2e/smoke_test.py   # type-check + browser E2E (needs both servers running)
```

The suite covers:

* electricity
* transport: return journeys, occupancy, flight bands and classes, radiative forcing, India and UK selection, proxies
* accommodation, food, waste and materials
* unit conversions
* missing and invalid data
* multiple factor versions and pinned recomputation
* totals and shares
* scenarios and recommendations
* the API, auth and admin protection
* CSV import
* dashboard-versus-PDF consistency
* **three sample conferences** (100, 500 and 2,000 participants), each checked against an independent hand calculation ([docs/sample_scenarios.md](docs/sample_scenarios.md))

## Deployment

The backend goes to **Render**:

1. `render.yaml` provisions the Docker web service and a managed PostgreSQL database.
2. Set `ADMIN_EMAIL`, `ADMIN_PASSWORD` and `CORS_ORIGINS` (the Vercel URL) in the dashboard. `SECRET_KEY` is generated for you.
3. Migrations and factor seeding run on boot.

The frontend goes to **Vercel**:

1. Import the `frontend/` directory (framework preset: Vite).
2. Set `VITE_API_URL=https://<render-service>.onrender.com`.
3. `vercel.json` provides the SPA rewrites.

Any Docker host works too: `docker compose up`, with nginx proxying `/api` to the backend.

## Project structure

```
backend/   FastAPI app: api/, models/, schemas/, services/ (emissions_engine, scenarios, recommendations,
           report_pdf, importer, distance, auth), calculations/ (factor_repository, units, geo), alembic/, tests/
frontend/  React + TypeScript + Tailwind + Recharts: pages/, forms/ (7 modules), dashboard/, charts/, services/, e2e/
data/      raw/ (original downloads) · processed/ (factor DB, cleaned CSVs, meal models, airports) · metadata/
           (source_registry, dataset_versions, data_quality) · samples/ (3 sample conferences) · reports/
docs/      methodology · calculation_formulas · data_sources · architecture · sample_scenarios ·
           DATASET_RESEARCH_AND_ACQUISITION_REPORT · sample_report_medium_corporate_500.pdf
scripts/   download_datasets · process_datasets · validate_datasets · import_emission_factors · generate_acquisition_report
```

## Completed features

* **Data pipeline.** 18 datasets downloaded with URL, date, size, SHA-256 and licence recorded. One failure is logged rather than hidden.
* **Factor database.** 416 versioned factor records (257 active), each with source, boundary, gases, methodology, derivation, pedigree data-quality score and licence.
* **Calculator modules.** 7 modules with:
  * tooltips, units on every field, optional fields and validation
  * autosave (on the device and on the server), back and next navigation, and a progress indicator
  * IATA airport search with automatic great-circle distances
  * optional geocoded road distance
  * CSV/Excel travel import with row-level errors and duplicate detection
* **Calculation engine.** Category-specific logic, unit conversion, occupancy, return trips, regional factor selection, CO₂→CO₂e conversion, missing-data handling, calculation log (formula on every line), and no double counting.
* **Dashboard:**
  * KPI cards
  * a donut, a category bar chart and a top-activities chart
  * actual-versus-estimated data and data quality
  * gross, market-based, offsets and net shown separately
  * a full traceable calculation table
  * assumptions and exclusions
* **What-if analysis.** 12 parameterised scenario presets plus a custom scenario builder. Recommendations are generated from the actual breakdown and quantified with the scenarios.
* **PDF report.** A GHG Protocol-style report built only from the stored calculation (it never recalculates), stored with a checksum, plus a reproducibility check against pinned factor versions.
* **Admin.** Add factor versions (immutable), activate or deactivate factors, bulk upload, browse sources, and view calculation history and statistics.

## Known limitations

* **Proxy factors.** No India-specific aviation, intercity coach, metro, waste-disposal or material factors are published, so UK DESNZ factors are used and flagged. Indian landfill emissions are probably **under-estimated**, because UK landfill gas capture is assumed.
* **Dated Indian factors.** The India GHG Program road and rail factors date from 2015 and were a consultation draft. The rail factor reflects the grid of that time.
* **Modelled meals.** Per-meal factors are modelled from the NIN plate composition and global food means. The 100 g protein portion and the snack composition are assumptions. Ingredient data from the caterer is more accurate.
* **Hotel benchmark.** The hotel factor is a 2021 national median; hotel class is not differentiated.
* **No residual mix.** Market-based electricity uses the grid average for non-certified kWh, because no Indian residual mix is published.
* **No numerical uncertainty.** Sources do not provide uncertainty ranges, so only a qualitative uncertainty rating is given.
* **Exclusions.** Virtual-participation emissions, well-to-tank and T&D emissions, printing energy and capital goods are excluded and disclosed.
* **Optional geocoding.** Road and rail distance estimation uses public OpenStreetMap services (Nominatim/OSRM). It is off by default; enable it with `ENABLE_ONLINE_GEOCODING=true` and respect their usage policies.
* **Not tested.** Docker images and the Render/Vercel deployment are configured but were not exercised in this environment, which has no Docker.
* **Unverified estimates.** Results are self-declared and unverified. Have them verified to ISO 14064-3 before making public claims.
