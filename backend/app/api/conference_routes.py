from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fastapi import APIRouter, Body, Depends, File, HTTPException, Response, UploadFile
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.api.deps import own_calculation, own_conference, parse_input
from app.config import ROOT
from app.database.session import get_db
from app.models import CalculationResultRow, Conference, GeneratedReport, ScenarioComparison, User
from app.schemas.conference import ConferenceInput
from app.schemas.results import CalculationResult
from app.services import conference_store, importer, recommendations, report_pdf, scenarios
from app.services.auth import current_user
from app.services.emissions_engine import EmissionsEngine, pins_from_result
from app.services.factor_service import get_repository

router = APIRouter(prefix="/api", tags=["conferences"])
SAMPLES_DIR = ROOT / "data" / "samples"


def _summary(c: Conference) -> dict:
    last = max(c.calculations, key=lambda x: x.id) if c.calculations else None
    return {"id": c.id, "name": c.name, "country": c.country, "state_city": c.state_city, "start_date": c.start_date,
            "end_date": c.end_date, "days": c.days, "format": c.format, "conference_type": c.conference_type,
            "current_step": c.current_step, "is_sample": c.is_sample, "updated_at": c.updated_at,
            "latest_calculation": {"id": last.id, "total_kg": last.total_kg, "created_at": last.created_at} if last else None}


# ------------------------------------------------------------------ stateless
@router.post("/calculate", response_model=CalculationResult)
def calculate_stateless(payload: dict = Body(...), db: Session = Depends(get_db)):
    """Calculate without saving (live preview, API clients)."""
    inp = parse_input(payload)
    return EmissionsEngine(get_repository(db)).calculate(inp)


@router.post("/validate")
def validate(payload: dict = Body(...)):
    from pydantic import ValidationError
    try:
        ConferenceInput.model_validate(payload)
        return {"valid": True, "errors": []}
    except ValidationError as ex:
        return {"valid": False, "errors": [{"loc": [str(x) for x in e["loc"]], "msg": e["msg"]} for e in ex.errors()]}


# ------------------------------------------------------------------ conferences CRUD
@router.get("/conferences")
def list_conferences(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(Conference).filter(Conference.owner_id == user.id).order_by(Conference.updated_at.desc()).all()
    return [_summary(c) for c in rows]


@router.post("/conferences")
def create_conference(payload: dict = Body(...), user: User = Depends(current_user), db: Session = Depends(get_db)):
    inp = parse_input(payload.get("input", payload))
    conf = Conference(owner_id=user.id, input_json={})
    conference_store.save(db, conf, inp, step=payload.get("current_step", 0))
    return {"id": conf.id, **_summary(conf), "input": conf.input_json}


@router.get("/conferences/{conf_id}")
def get_conference(conf: Conference = Depends(own_conference)):
    return {**_summary(conf), "input": conf.input_json}


@router.put("/conferences/{conf_id}")
def update_conference(payload: dict = Body(...), conf: Conference = Depends(own_conference), db: Session = Depends(get_db)):
    inp = parse_input(payload.get("input", payload))
    conference_store.save(db, conf, inp, step=payload.get("current_step"))
    return {**_summary(conf), "input": conf.input_json}


@router.delete("/conferences/{conf_id}", status_code=204)
def delete_conference(conf: Conference = Depends(own_conference), db: Session = Depends(get_db)):
    db.delete(conf)
    db.commit()
    return Response(status_code=204)


# ------------------------------------------------------------------ calculations
@router.post("/conferences/{conf_id}/calculate")
def calculate(conf: Conference = Depends(own_conference), db: Session = Depends(get_db)):
    inp = parse_input(conf.input_json)
    repo = get_repository(db)
    result = EmissionsEngine(repo).calculate(inp)
    scen = scenarios.run_all(inp, repo)
    recs = recommendations.generate(result, scen)
    row = CalculationResultRow(conference_id=conf.id, input_snapshot=conf.input_json, result=result.model_dump(mode="json"),
                               recommendations=recs, total_kg=result.total_kg, factor_set_version=result.factor_set_version,
                               engine_version=result.engine_version)
    db.add(row)
    db.flush()
    for s in scen:
        if not s.get("error"):
            db.add(ScenarioComparison(calculation_id=row.id, preset=s["preset"], params=s.get("params"), result=s,
                                      reduction_kg=s.get("reduction_kg", 0)))
    db.commit()
    return _calc_out(row)


def _calc_out(row: CalculationResultRow) -> dict:
    return {"id": row.id, "conference_id": row.conference_id, "created_at": row.created_at, "result": row.result,
            "recommendations": row.recommendations,
            "scenarios": [s.result for s in sorted(row.scenarios, key=lambda x: x.id)],
            "reports": [{"id": r.id, "filename": r.filename, "created_at": r.created_at, "sha256": r.sha256} for r in row.reports]}


@router.get("/conferences/{conf_id}/calculations")
def list_calculations(conf: Conference = Depends(own_conference)):
    return [{"id": c.id, "total_kg": c.total_kg, "factor_set_version": c.factor_set_version, "engine_version": c.engine_version,
             "created_at": c.created_at} for c in sorted(conf.calculations, key=lambda x: -x.id)]


@router.get("/calculations/{calc_id}")
def get_calculation(calc: CalculationResultRow = Depends(own_calculation)):
    return _calc_out(calc)


@router.get("/calculations/{calc_id}/verify")
def verify_reproducibility(calc: CalculationResultRow = Depends(own_calculation), db: Session = Depends(get_db)):
    """Recompute from the stored input snapshot with the SAME (pinned) factor ids and compare."""
    inp = parse_input(calc.input_snapshot)
    repo = get_repository(db)
    pinned = pins_from_result(calc.result)
    try:
        again = EmissionsEngine(repo, pinned=pinned).calculate(inp)
    except KeyError as ex:
        return {"reproducible": False, "reason": str(ex)}
    current = EmissionsEngine(repo).calculate(inp)
    return {"reproducible": abs(again.total_kg - calc.total_kg) < 1e-6, "stored_total_kg": calc.total_kg,
            "recomputed_with_pinned_factors_kg": again.total_kg, "recomputed_with_current_factors_kg": current.total_kg,
            "factors_changed_since": sorted({f["factor_key"] for f in current.model_dump()["factors_used"]
                                             if pinned.get(f["factor_key"]) not in (None, f["factor_id"])})}


@router.post("/calculations/{calc_id}/scenarios")
def run_scenario(payload: dict = Body(...), calc: CalculationResultRow = Depends(own_calculation), db: Session = Depends(get_db)):
    """Body: {"preset": "shared_transport", "params": {...}}  or  {"scenario_input": {...full ConferenceInput...}, "title": "..."}"""
    base = parse_input(calc.input_snapshot)
    repo = get_repository(db)
    pinned = pins_from_result(calc.result)
    baseline = EmissionsEngine(repo, pinned=pinned).calculate(base)
    if "scenario_input" in payload:
        scen_inp = parse_input(payload["scenario_input"])
        res = scenarios.compare(base, scen_inp, repo, title=payload.get("title", "Custom scenario"),
                                description=payload.get("description", "User-edited arrangement"), baseline_result=baseline)
    else:
        try:
            res = scenarios.run_scenario(base, payload.get("preset", ""), payload.get("params"), repo, baseline_result=baseline)
        except KeyError as ex:
            raise HTTPException(400, str(ex))
    db.add(ScenarioComparison(calculation_id=calc.id, preset=res["preset"], params=res.get("params"), result=res,
                              reduction_kg=res["reduction_kg"]))
    db.commit()
    return res


@router.get("/scenario-presets")
def scenario_presets():
    return [{"preset": k, "title": v["title"], "category": v["category"], "params": v["params"]} for k, v in scenarios.PRESETS.items()]


# ------------------------------------------------------------------ reports
@router.post("/calculations/{calc_id}/report")
def generate_report(calc: CalculationResultRow = Depends(own_calculation), db: Session = Depends(get_db)):
    scen = [s.result for s in sorted(calc.scenarios, key=lambda x: x.id) if s.preset in scenarios.PRESETS][:len(scenarios.PRESETS)]
    pdf = report_pdf.build_pdf(calc.input_snapshot, calc.result, scen, calc.recommendations or [], calc.id)
    safe = "".join(ch if ch.isalnum() else "_" for ch in calc.result["conference_name"])[:60]
    rep = GeneratedReport(calculation_id=calc.id, filename=f"{safe}_carbon_report_calc{calc.id}.pdf",
                          sha256=hashlib.sha256(pdf).hexdigest(), size_bytes=len(pdf), pdf=pdf)
    db.add(rep)
    db.commit()
    return {"id": rep.id, "filename": rep.filename, "sha256": rep.sha256, "size_bytes": rep.size_bytes, "created_at": rep.created_at}


@router.get("/reports/{report_id}/download")
def download_report(report_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    rep = db.get(GeneratedReport, report_id)
    if not rep:
        raise HTTPException(404, "Report not found")
    calc = db.get(CalculationResultRow, rep.calculation_id)
    if calc.conference.owner_id != user.id and user.role != "admin":
        raise HTTPException(404, "Report not found")
    return Response(rep.pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{rep.filename}"'})


# ------------------------------------------------------------------ imports
@router.post("/imports/transport")
async def import_transport(file: UploadFile = File(...), trip_type: str = "return", user: User = Depends(current_user)):
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 10 MB)")
    try:
        return importer.import_transport(content, file.filename or "upload.csv", trip_type)
    except ValueError as ex:
        raise HTTPException(400, str(ex))


@router.get("/imports/transport/template", response_class=PlainTextResponse)
def transport_template():
    return PlainTextResponse(importer.TEMPLATE_CSV, media_type="text/csv",
                             headers={"Content-Disposition": 'attachment; filename="travel_import_template.csv"'})


# ------------------------------------------------------------------ samples
@router.get("/samples")
def list_samples():
    out = []
    for p in sorted(SAMPLES_DIR.glob("*.json")):
        d = json.loads(p.read_text())
        out.append({"id": p.stem, "title": d["title"], "description": d["description"],
                    "participants": d["input"]["basic"]["attendees"]})
    return out


@router.post("/samples/{sample_id}/load")
def load_sample(sample_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = SAMPLES_DIR / f"{Path(sample_id).name}.json"
    if not p.exists():
        raise HTTPException(404, "Sample not found")
    d = json.loads(p.read_text())
    inp = parse_input(d["input"])
    conf = Conference(owner_id=user.id, input_json={}, is_sample=True)
    conference_store.save(db, conf, inp, step=7)
    return {"id": conf.id, **_summary(conf), "input": conf.input_json}
