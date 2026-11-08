from __future__ import annotations

import io
import json
from datetime import date

import pandas as pd
from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.calculations.geo import search_airports
from app.config import ROOT
from app.database.session import get_db
from app.models import CalculationResultRow, Conference, EmissionFactor, EmissionFactorSource, User
from app.services import distance
from app.services.auth import admin_user
from app.services.factor_service import get_repository, import_factors, invalidate

router = APIRouter(prefix="/api", tags=["factors & reference data"])


# ------------------------------------------------------------------ public read-only
@router.get("/factors")
def list_factors(category: str | None = None, q: str | None = None, include_inactive: bool = False,
                 limit: int = Query(500, le=2000), db: Session = Depends(get_db)):
    qry = db.query(EmissionFactor)
    if not include_inactive:
        qry = qry.filter(EmissionFactor.is_active.is_(True))
    if category:
        qry = qry.filter(EmissionFactor.category == category)
    rows = qry.order_by(EmissionFactor.factor_key).limit(limit).all()
    out = [r.to_record() for r in rows]
    if not rows:  # unseeded DB - serve from JSON
        out = [f.raw for f in get_repository(db).all() if include_inactive or f.is_active]
        if category:
            out = [f for f in out if f["category"] == category]
    if q:
        ql = q.lower()
        out = [f for f in out if ql in f["factor_key"].lower() or ql in f["subcategory"].lower() or ql in f["source_name"].lower()]
    return out


@router.get("/factors/{factor_id:path}")
def get_factor(factor_id: str, db: Session = Depends(get_db)):
    r = db.query(EmissionFactor).filter(EmissionFactor.factor_id == factor_id).first()
    if not r:
        raise HTTPException(404, "Factor not found")
    return r.to_record()


@router.get("/sources")
def list_sources(db: Session = Depends(get_db)):
    rows = db.query(EmissionFactorSource).order_by(EmissionFactorSource.source_id).all()
    return [{c: getattr(r, c) for c in ("source_id", "name", "publisher", "url", "landing_page", "licence", "version",
                                        "reporting_year", "geography", "local_path", "sha256", "downloaded_at", "status", "notes")}
            for r in rows]


@router.get("/dataset-versions")
def dataset_versions():
    return json.loads((ROOT / "data" / "metadata" / "dataset_versions.json").read_text())


@router.get("/meta/options")
def options(db: Session = Depends(get_db)):
    """Everything the forms need to render dropdowns from the live factor database."""
    repo = get_repository(db)
    act = repo.active()
    food = [{"key": f.factor_key, "label": f.subcategory, "factor": f.value, "unit": f.unit}
            for f in act if f.category == "food" and f.activity == "Food product"]
    meals = [{"key": f.factor_key.replace("food.meal.", ""), "label": f.subcategory, "factor": f.value}
             for f in act if f.factor_key.startswith("food.meal.")]
    materials = [{"key": f.factor_key, "label": f.subcategory, "factor": f.value, "unit": f.unit}
                 for f in act if f.category == "materials"]
    hotels = sorted([{"country": f.raw.get("country") or f.geography, "factor": f.value, "key": f.factor_key}
                     for f in act if f.factor_key.startswith("accommodation.hotel.")], key=lambda x: x["country"])
    waste_routes: dict[str, list[str]] = {}
    for f in act:
        if f.factor_key.startswith("waste."):
            _, mat, route = f.factor_key.split(".", 2)
            route = "recycling" if route.startswith("recycling") else route
            waste_routes.setdefault(mat, [])
            if route not in waste_routes[mat]:
                waste_routes[mat].append(route)
    grid = [{"country_code": "IN", "factor": repo.get("electricity.grid.IN").value, "source": "CEA v22.0 FY2025-26"},
            {"country_code": "GB", "factor": repo.get("electricity.grid.GB").value, "source": "DESNZ 2026"}]
    grid_years = sorted(k.split(".FY")[1] for k in repo.keys_with_prefix("electricity.grid.IN.FY"))
    return {"food_items": sorted(food, key=lambda x: x["label"]), "meal_models": meals, "materials": materials,
            "hotel_countries": hotels, "waste_routes": waste_routes, "grid_factors": grid, "grid_years": grid_years,
            "factor_set_version": repo.factor_set_version}


@router.get("/meta/airports")
def airports(q: str = Query(..., min_length=1)):
    return search_airports(q)


@router.get("/meta/distance")
def estimate_distance(origin: str, destination: str, mode: str = "flight"):
    return distance.estimate(origin, destination, mode)


# ------------------------------------------------------------------ admin (protected)
class FactorIn(BaseModel):
    factor_key: str = Field(pattern=r"^[a-z0-9_.A-Z-]+$", max_length=120)
    category: str
    activity: str
    subcategory: str
    emission_factor: float = Field(ge=0)
    activity_unit: str
    gas_basis: str = "CO2e"
    geography: str
    reporting_year: str
    source_name: str = Field(min_length=3)
    source_url: str = Field(min_length=8)
    source_publisher: str | None = None
    source_reference: str | None = None
    dataset_version: str = Field(min_length=1, max_length=60)
    system_boundary: str = Field(min_length=3)
    greenhouse_gases_included: str = "CO2, CH4, N2O"
    methodology: str = Field(min_length=3)
    uncertainty: str | None = None
    licence: str = "See source"
    data_quality_label: str = Field(default="medium", pattern="^(high|medium|low)$")
    activate: bool = True


@router.post("/admin/factors")
def admin_add_factor(f: FactorIn, admin: User = Depends(admin_user), db: Session = Depends(get_db)):
    """Add a new factor or a new VERSION of an existing key. Existing records are never edited in place."""
    fid = f"{f.factor_key}@{f.dataset_version}"
    if db.query(EmissionFactor).filter(EmissionFactor.factor_id == fid).first():
        raise HTTPException(409, f"{fid} already exists - use a new dataset_version")
    score = {"high": 1.5, "medium": 2.5, "low": 3.5}[f.data_quality_label]
    row = EmissionFactor(
        factor_id=fid, factor_key=f.factor_key, category=f.category, activity=f.activity, subcategory=f.subcategory,
        emission_factor=f.emission_factor, unit=f"kg {f.gas_basis}/{f.activity_unit}", activity_unit=f.activity_unit,
        gas_basis=f.gas_basis, geography=f.geography, reporting_year=f.reporting_year, source_id=f"ADMIN:{f.dataset_version}",
        source_name=f.source_name, source_publisher=f.source_publisher, source_url=f.source_url,
        source_reference=f.source_reference, dataset_version=f.dataset_version, system_boundary=f.system_boundary,
        greenhouse_gases_included=f.greenhouse_gases_included, methodology=f.methodology, derivation=None,
        data_quality={"label": f.data_quality_label, "score": score, "note": "Admin-entered"}, uncertainty=f.uncertainty,
        licence=f.licence, last_updated=date.today().isoformat(), is_active=False, created_by=admin.email)
    db.add(row)
    db.flush()
    if f.activate:
        _activate(db, row)
    db.commit()
    invalidate()
    return row.to_record()


def _activate(db: Session, row: EmissionFactor):
    db.query(EmissionFactor).filter(EmissionFactor.factor_key == row.factor_key, EmissionFactor.id != row.id) \
        .update({"is_active": False})
    row.is_active = True


@router.post("/admin/factors/{factor_id:path}/activate")
def admin_activate(factor_id: str, admin: User = Depends(admin_user), db: Session = Depends(get_db)):
    row = db.query(EmissionFactor).filter(EmissionFactor.factor_id == factor_id).first()
    if not row:
        raise HTTPException(404, "Factor not found")
    _activate(db, row)
    db.commit()
    invalidate()
    return row.to_record()


@router.post("/admin/factors/{factor_id:path}/deactivate")
def admin_deactivate(factor_id: str, admin: User = Depends(admin_user), db: Session = Depends(get_db)):
    row = db.query(EmissionFactor).filter(EmissionFactor.factor_id == factor_id).first()
    if not row:
        raise HTTPException(404, "Factor not found")
    row.is_active = False
    db.commit()
    invalidate()
    return row.to_record()


@router.post("/admin/factors/import")
def admin_reimport(admin: User = Depends(admin_user), db: Session = Depends(get_db)):
    """Re-seed official factors from data/processed/emission_factors.json (admin factors are kept)."""
    return import_factors(db)


@router.post("/admin/factors/upload")
async def admin_upload_factors(file: UploadFile = File(...), admin: User = Depends(admin_user), db: Session = Depends(get_db)):
    """Bulk-add factors from CSV/XLSX with the FactorIn columns. Invalid rows are reported, valid rows added."""
    content = await file.read()
    name = (file.filename or "").lower()
    df = pd.read_excel(io.BytesIO(content)) if name.endswith((".xlsx", ".xls")) else pd.read_csv(io.BytesIO(content))
    added, errors = [], []
    for i, r in df.iterrows():
        try:
            data = {k: (None if pd.isna(v) else v) for k, v in r.to_dict().items()}
            data["reporting_year"] = str(data.get("reporting_year"))
            res = admin_add_factor(FactorIn.model_validate(data), admin, db)
            added.append(res["factor_id"])
        except Exception as ex:  # report every bad row
            db.rollback()
            errors.append({"row": int(i) + 2, "message": str(ex)[:300]})
    return {"added": added, "errors": errors}


@router.get("/admin/calculations")
def admin_calculations(limit: int = 100, admin: User = Depends(admin_user), db: Session = Depends(get_db)):
    rows = db.query(CalculationResultRow).order_by(CalculationResultRow.id.desc()).limit(limit).all()
    return [{"id": r.id, "conference_id": r.conference_id, "conference": r.conference.name, "owner_id": r.conference.owner_id,
             "total_kg": r.total_kg, "factor_set_version": r.factor_set_version, "engine_version": r.engine_version,
             "created_at": r.created_at} for r in rows]


@router.get("/admin/stats")
def admin_stats(admin: User = Depends(admin_user), db: Session = Depends(get_db)):
    return {"users": db.query(User).count(), "conferences": db.query(Conference).count(),
            "calculations": db.query(CalculationResultRow).count(),
            "factors_total": db.query(EmissionFactor).count(),
            "factors_active": db.query(EmissionFactor).filter(EmissionFactor.is_active.is_(True)).count(),
            "factors_admin": db.query(EmissionFactor).filter(EmissionFactor.created_by.isnot(None)).count()}
