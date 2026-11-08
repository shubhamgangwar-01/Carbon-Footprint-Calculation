#!/usr/bin/env python3
"""Load data/processed/emission_factors.json and the source registry into the database.

Usage:  python scripts/import_emission_factors.py   (uses DATABASE_URL)

Official (seeded) factors are replaced; administrator-created factors are kept.
Run `alembic upgrade head` (from backend/) first.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.database.session import SessionLocal  # noqa: E402
from app.services.factor_service import import_factors  # noqa: E402

if __name__ == "__main__":
    with SessionLocal() as db:
        print(import_factors(db))
