# Architecture

```
                     ┌──────────────────────────── data pipeline (offline) ────────────────────────────┐
 official sources ──►│ download_datasets.py → data/raw/* (unmodified, SHA-256) → source_registry.json   │
 (CEA, DESNZ, IGHGP, │ process_datasets.py  → data/processed/emission_factors.json (+ per-category CSV)  │
  OWID, NIN, EPA…)   │ validate_datasets.py → integrity, cross-checks, spot values                       │
                     │ import_emission_factors.py → PostgreSQL emission_factors / _sources               │
                     └──────────────────────────────────────────────────────────────────────────────────┘
                                                     │
┌──────────── React + TS + Tailwind (Vite) ─────────┐ │  ┌────────────── FastAPI (Python) ───────────────────┐
│ Landing · 7-step wizard (autosave) · Review       │ │  │ api/ auth · conferences · calculate · scenarios   │
│ Dashboard (Recharts) · What-if · Report · Admin   │◄┼─►│      imports · reports · factors · admin          │
│ Methodology & factor browser                      │ │  │ services/ emissions_engine (pure)                 │
└────────────────────────────────────────────────────┘ │  │           scenarios · recommendations · report_pdf│
                                                       │  │           importer · distance · factor_service    │
                                                       │  │ calculations/ factor_repository · units · geo     │
                                                       └─►│ models/ SQLAlchemy  ·  alembic/ migrations        │
                                                          └──────────────────────┬────────────────────────────┘
                                                                                 ▼
                                                                        PostgreSQL 16/17
```

## Components

* **Calculation engine.** `backend/app/services/emissions_engine.py` is a pure function: it takes a `ConferenceInput` and a `FactorRepository` and returns a `CalculationResult`. It has no database or network access, which keeps it unit-testable and reusable from the API, the scenario engine and the tests.
* **Factor repository.** `calculations/factor_repository.py` resolves a logical `factor_key` to exactly one active record. It accepts a *pin map* (key → factor_id) to recompute a stored calculation with the exact historical factors. Factor records are immutable: admins add new versions and activate them.
* **Scenarios.** `services/scenarios.py` applies pure transformations to a copy of the input and runs it through the same engine and factor set.
* **Recommendations.** `services/recommendations.py` holds rules triggered by this conference's category and activity shares and quantified by the scenario results. Nothing is generic.
* **PDF report.** `services/report_pdf.py` uses ReportLab with matplotlib charts. It renders only from a stored calculation, so dashboard and PDF always agree.
* **Importer.** `services/importer.py` handles CSV/XLSX travel import: column aliasing, unit and value normalisation, per-row schema validation, duplicate detection, and row-numbered error reports.
* **Distance.** Flight distances are computed offline from OurAirports data. Road/rail distances come from optional Nominatim + OSRM lookups, enabled by an environment variable, and are labelled as estimates.
* **Auth.** PBKDF2 password hashes and HMAC-signed tokens. Guest sessions are created automatically. Admin endpoints require the `admin` role, and the admin account is created from `ADMIN_EMAIL` / `ADMIN_PASSWORD`.

## Database (Alembic migration `alembic/versions/*_initial_schema.py`)

| Table | Purpose |
|---|---|
| users | guest / user / admin accounts |
| conferences | conference header and `input_json` (source of truth for recalculation) |
| conference_participants | counts by group |
| transportation_entries, accommodation_entries, energy_entries, food_entries, waste_entries, material_entries | normalised module data (rewritten with `input_json` in one transaction) |
| emission_factor_sources | registry of datasets: URL, licence, version, SHA-256, status |
| emission_factors | every factor version (`factor_id = key@dataset_version`, `is_active`, `created_by` for admin entries) |
| calculation_results | input snapshot, full result JSON (lines carry factor ids/values), recommendations, factor-set and engine versions |
| scenario_comparisons | each scenario run for a calculation |
| generated_reports | PDF bytes, filename, SHA-256 |

## Key API endpoints

| Method | Path | |
|---|---|---|
| POST | /api/auth/guest · /register · /login · /upgrade | sessions |
| GET/POST/PUT/DELETE | /api/conferences[/{id}] | save progress |
| POST | /api/conferences/{id}/calculate | store result + scenarios + recommendations |
| POST | /api/calculate · /api/validate | stateless preview / validation |
| GET | /api/calculations/{id} · /verify | result · reproducibility check |
| POST | /api/calculations/{id}/scenarios | preset or custom scenario |
| POST/GET | /api/calculations/{id}/report · /api/reports/{id}/download | PDF |
| POST/GET | /api/imports/transport · /template | bulk travel import |
| GET | /api/factors · /sources · /dataset-versions · /meta/options · /meta/airports · /meta/distance | reference data |
| POST | /api/admin/factors · /{id}/activate · /{id}/deactivate · /import · /upload | protected factor management |
| GET | /api/admin/calculations · /stats | history |

OpenAPI docs are served at `http://localhost:8000/docs`.
