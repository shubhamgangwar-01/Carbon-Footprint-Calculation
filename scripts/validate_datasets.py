#!/usr/bin/env python3
"""Validate the emission-factor database and raw-file integrity.

Checks
* every raw file in source_registry.json exists and matches its recorded SHA-256
* every factor has a source, URL, unit, boundary, data-quality and a positive finite value
* exactly one active factor per factor_key
* units follow 'kg CO2e/<unit>' (or kg CO2/ for published CO2-only records)
* CEA workbook and user-guide values agree for every year (|diff| <= 0.001)
* spot checks against values read manually from the original documents
Exit code 1 on any failure.
"""
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
errors: list[str] = []
ok = lambda m: print(f"  ok  {m}")  # noqa: E731


def fail(m):
    errors.append(m)
    print(f"  FAIL {m}")


reg = json.loads((ROOT / "data/metadata/source_registry.json").read_text())
print("Raw file integrity")
for s in reg["sources"]:
    if s["status"] != "downloaded":
        print(f"  --  {s['source_id']}: not downloaded ({s.get('error')}) - recorded as failed acquisition")
        continue
    p = ROOT / s["local_path"]
    if not p.exists():
        fail(f"{s['source_id']}: file missing {p}")
        continue
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    (ok if h == s["sha256"] else fail)(f"{s['source_id']}: sha256 {'matches' if h == s['sha256'] else 'MISMATCH'}")

db = json.loads((ROOT / "data/processed/emission_factors.json").read_text())
F = db["factors"]
print(f"\nFactor records: {len(F)}")
req = ["factor_id", "factor_key", "category", "emission_factor", "unit", "geography", "reporting_year", "source_name",
       "source_url", "dataset_version", "system_boundary", "greenhouse_gases_included", "methodology", "data_quality", "licence"]
bad = 0
for f in F:
    for k in req:
        if f.get(k) in (None, ""):
            fail(f"{f['factor_id']}: missing {k}")
            bad += 1
    v = f["emission_factor"]
    if not (isinstance(v, (int, float)) and math.isfinite(v) and v >= 0):
        fail(f"{f['factor_id']}: invalid value {v}")
    if f["category"] != "parameter" and not (f["unit"].startswith("kg CO2e/") or f["unit"].startswith("kg CO2/")):
        fail(f"{f['factor_id']}: unexpected unit {f['unit']}")
if not bad:
    ok("all factors have source, URL, unit, boundary, gases, methodology, data quality and licence")
active = Counter(f["factor_key"] for f in F if f["is_active"])
dups = [k for k, n in active.items() if n > 1]
(fail(f"multiple active factors: {dups}") if dups else ok("exactly one active factor per key"))

import csv  # noqa: E402
print("\nCEA cross-check (workbook vs user guide Annexure-I)")
# Annexure-I footnote: "From the years 2022-23 onwards, total CO2 emissions and total net electricity generation
# figures are adjusted for cross-border electricity transfers" -> compare earlier years with the unadjusted column.
with open(ROOT / "data/processed/electricity/india_grid_emission_factor_series_CEA_v22.csv") as fh:
    for r in csv.DictReader(fh):
        adjusted = int(r["fiscal_year"][:4]) >= 2022
        col = "weighted_avg_incl_RE_captive_incl_imports_tCO2_per_MWh" if adjusted else "weighted_avg_incl_RE_captive_excl_imports_tCO2_per_MWh"
        a, b = float(r[col]), float(r["user_guide_annexure_I_tCO2_per_MWh"])
        # guide values are 3-dp ratios of rounded Mt/BU totals (e.g. 888.34/1154.39 = 0.7695 -> 0.770), so allow 0.001
        (ok if abs(a - b) <= 0.001 + 1e-9 else fail)(
            f"FY {r['fiscal_year']}: workbook {a:.4f} ({'cross-border adjusted' if adjusted else 'unadjusted'}) vs guide {b:.3f}")

print("\nSpot checks against original documents")
by_key = {f["factor_key"]: f for f in F if f["is_active"]}
spot = {
    "electricity.grid.IN.co2": (0.675, "CEA v22 Annexure-I FY2025-26"),
    "accommodation.hotel.india": (58.9, "DESNZ 2026 Hotel stay India"),
    "transport.flight.long_haul_uk.economy.with_rf": (0.11704, "DESNZ 2026 ID 21_316_3170_11_1"),
    "transport.bus.coach.uk": (0.03948, "DESNZ 2026 coach"),
    "food.beef": (99.48, "OWID Poore & Nemecek beef herd"),
    "energy.fuel.diesel.litre": (2.66155, "DESNZ 2026 diesel 100% mineral"),
}
for k, (exp, src) in spot.items():
    got = by_key[k]["emission_factor"]
    (ok if abs(got - exp) < 1e-6 else fail)(f"{k} = {got} (expected {exp}, {src})")
rail = by_key["transport.rail.national.IN"]["derivation"]["published"]
(ok if rail == 0.007837 else fail)(f"India rail published value {rail} (expected 0.007837 kg CO2/pkm, IndiaGHGP 2014-15)")

print(f"\n{'FAILED' if errors else 'PASSED'}: {len(errors)} error(s)")
sys.exit(1 if errors else 0)
