"""Bridges the emission_factors table and the in-memory FactorRepository."""
from __future__ import annotations

import json
import threading
from pathlib import Path

from sqlalchemy.orm import Session

from app.calculations.factor_repository import FactorRepository
from app.config import ROOT, get_settings
from app.models import EmissionFactor, EmissionFactorSource

_lock = threading.Lock()
_cache: dict[str, FactorRepository] = {}

CORE_COLS = {"factor_id", "factor_key", "category", "activity", "subcategory", "emission_factor", "unit", "activity_unit",
             "gas_basis", "geography", "reporting_year", "source_id", "source_name", "source_publisher", "source_url",
             "source_reference", "dataset_version", "system_boundary", "greenhouse_gases_included", "methodology",
             "derivation", "data_quality", "uncertainty", "licence", "last_updated", "is_active"}


def invalidate():
    with _lock:
        _cache.clear()


def get_repository(db: Session) -> FactorRepository:
    with _lock:
        if "db" in _cache:
            return _cache["db"]
        rows = db.query(EmissionFactor).all()
        if rows:
            repo = FactorRepository([r.to_record() for r in rows], factor_set_version=_factor_set_version(rows))
        else:  # database not yet seeded - fall back to the processed JSON (read-only)
            repo = FactorRepository.from_json(get_settings().factors_json)
        _cache["db"] = repo
        return repo


def _factor_set_version(rows) -> str:
    custom = [r for r in rows if r.created_by]
    base = "FS-2026.1"
    if custom:
        latest = max(r.created_at for r in custom)
        return f"{base}+admin.{latest.strftime('%Y%m%d%H%M%S')}"
    return base


def import_factors(db: Session, path: Path | None = None, replace_seeded: bool = True) -> dict:
    """Load data/processed/emission_factors.json + source registry into the DB.
    Admin-created factors (created_by set) are never deleted by a re-import."""
    path = path or get_settings().factors_json
    db_json = json.loads(Path(path).read_text())
    reg_path = ROOT / "data" / "metadata" / "source_registry.json"
    registry = json.loads(reg_path.read_text()) if reg_path.exists() else {"sources": []}
    n_src = 0
    for s in registry["sources"]:
        row = db.query(EmissionFactorSource).filter_by(source_id=s["source_id"]).first() or EmissionFactorSource(source_id=s["source_id"])
        row.name, row.publisher, row.url = s["name"], s.get("publisher"), s.get("url")
        row.landing_page, row.licence, row.version = s.get("landing_page"), s.get("licence"), s.get("version")
        row.reporting_year, row.geography, row.local_path = s.get("reporting_year"), s.get("geography"), s.get("local_path")
        row.sha256, row.downloaded_at = s.get("sha256"), s.get("downloaded_at") or s.get("attempted_at")
        row.status, row.notes = s.get("status"), s.get("notes") or s.get("error")
        db.add(row)
        n_src += 1
    # literature / derived sources referenced by factors but not downloadable files
    for f in db_json["factors"]:
        if not db.query(EmissionFactorSource).filter_by(source_id=f["source_id"]).first() and \
                f["source_id"] not in {s["source_id"] for s in registry["sources"]}:
            db.add(EmissionFactorSource(source_id=f["source_id"], name=f["source_name"], publisher=f.get("source_publisher"),
                                        url=f.get("source_url"), landing_page=f.get("source_landing_page"),
                                        licence=f.get("licence"), version=f.get("dataset_version"),
                                        reporting_year=str(f.get("reporting_year")), geography=f.get("geography"),
                                        status="literature/derived", notes="Not a downloadable dataset; see factor derivation."))
            db.flush()
    if replace_seeded:
        db.query(EmissionFactor).filter(EmissionFactor.created_by.is_(None)).delete()
    existing = {r.factor_id for r in db.query(EmissionFactor.factor_id).all()}
    n = 0
    for f in db_json["factors"]:
        if f["factor_id"] in existing:
            continue
        core = {k: f.get(k) for k in CORE_COLS}
        core["reporting_year"] = str(core["reporting_year"])
        extra = {k: v for k, v in f.items() if k not in CORE_COLS and k != "source_landing_page"}
        db.add(EmissionFactor(**core, extra=extra or None))
        n += 1
    # an admin factor that is active supersedes the seeded active factor with the same key
    for adm in db.query(EmissionFactor).filter(EmissionFactor.created_by.isnot(None), EmissionFactor.is_active.is_(True)).all():
        db.query(EmissionFactor).filter(EmissionFactor.factor_key == adm.factor_key, EmissionFactor.id != adm.id,
                                        EmissionFactor.is_active.is_(True)).update({"is_active": False})
    db.commit()
    invalidate()
    return {"factors_imported": n, "sources": n_src, "factor_set_version": db_json.get("factor_set_version")}
