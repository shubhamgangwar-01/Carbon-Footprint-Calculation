"""API integration tests against a throw-away database
(TEST_DATABASE_URL, default: local PostgreSQL 'conference_carbon_test', falling back to SQLite)."""
import io
import os
import re

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app.database.session import Base, get_db, make_engine
from app.main import app
from app.models import User
from app.services import factor_service
from app.services.auth import hash_password


def _engine():
    url = os.getenv("TEST_DATABASE_URL", "postgresql+psycopg://localhost:5432/conference_carbon_test")
    try:
        eng = make_engine(url)
        with eng.connect() as c:
            c.execute(text("select 1"))
        return eng
    except Exception:
        return make_engine("sqlite:///./test_api.sqlite3")


@pytest.fixture(scope="module")
def client():
    eng = _engine()
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    TS = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)

    def override():
        db = TS()
        try:
            yield db
        finally:
            db.close()

    with TS() as db:
        factor_service.import_factors(db)
        db.add(User(email="admin@test.org", password_hash=hash_password("admin-pass-123"), role="admin"))
        db.commit()
    app.dependency_overrides[get_db] = override
    yield TestClient(app)   # no context manager => lifespan (migrations on the dev DB) is not run
    app.dependency_overrides.clear()
    factor_service.invalidate()
    Base.metadata.drop_all(eng)


@pytest.fixture(scope="module")
def guest(client):
    t = client.post("/api/auth/guest").json()["token"]
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture(scope="module")
def admin(client):
    t = client.post("/api/auth/login", json={"email": "admin@test.org", "password": "admin-pass-123"}).json()["token"]
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture(scope="module")
def sample_calc(client, guest):
    conf = client.post("/api/samples/medium_corporate_500/load", headers=guest).json()
    calc = client.post(f"/api/conferences/{conf['id']}/calculate", headers=guest).json()
    return conf, calc


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_auth_required(client):
    assert client.get("/api/conferences").status_code == 401
    assert client.get("/api/conferences", headers={"Authorization": "Bearer forged.token.1.x"}).status_code == 401


def test_register_and_login(client):
    r = client.post("/api/auth/register", json={"email": "a@b.org", "password": "longpassword"})
    assert r.status_code == 200
    assert client.post("/api/auth/register", json={"email": "a@b.org", "password": "longpassword"}).status_code == 409
    assert client.post("/api/auth/login", json={"email": "a@b.org", "password": "wrongpassword"}).status_code == 401


def test_stateless_calculate_and_validation(client):
    ok = client.post("/api/calculate", json={"basic": {"name": "x", "attendees": 10, "days": 1},
                                             "energy": {"grid_electricity_kwh": 100}})
    assert ok.status_code == 200 and ok.json()["total_kg"] > 0
    bad = client.post("/api/calculate", json={"basic": {"name": "x", "attendees": -1, "days": 1}})
    assert bad.status_code == 422
    v = client.post("/api/validate", json={"basic": {"name": "x", "attendees": 1, "days": 1},
                                           "waste": {"entries": [{"material": "food", "generated_kg": 1, "landfill_kg": 5}]}}).json()
    assert not v["valid"] and "exceeds" in v["errors"][0]["msg"]


def test_conference_crud_and_isolation(client, guest):
    payload = {"input": {"basic": {"name": "My conf", "attendees": 50, "days": 2}}, "current_step": 1}
    c = client.post("/api/conferences", json=payload, headers=guest).json()
    assert c["name"] == "My conf" and c["current_step"] == 1
    payload["input"]["transport"] = [{"mode": "train", "distance_km": 100, "passengers": 5}]
    u = client.put(f"/api/conferences/{c['id']}", json=payload, headers=guest).json()
    assert len(u["input"]["transport"]) == 1
    other = {"Authorization": "Bearer " + client.post("/api/auth/guest").json()["token"]}
    assert client.get(f"/api/conferences/{c['id']}", headers=other).status_code == 404
    assert client.delete(f"/api/conferences/{c['id']}", headers=guest).status_code == 204


def test_dashboard_matches_engine_and_pdf(client, guest, sample_calc):
    conf, calc = sample_calc
    res = calc["result"]
    assert res["total_kg"] == pytest.approx(sum(l["emissions_kg"] for l in res["lines"]), abs=1e-3)
    assert res["total_kg"] == pytest.approx(sum(c["emissions_kg"] for c in res["by_category"]), abs=1e-3)
    rep = client.post(f"/api/calculations/{calc['id']}/report", headers=guest).json()
    pdf = client.get(f"/api/reports/{rep['id']}/download", headers=guest)
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    text_ = " ".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf.content)).pages)
    assert f"{res['total_tonnes']:,.2f}" in text_                      # headline total
    for c in res["by_category"]:
        assert f"{c['emissions_kg']:,.1f}" in text_                     # category table
    assert "Calculation #" + str(calc["id"]) in text_


def test_reproducibility_after_factor_update(client, guest, admin, sample_calc):
    conf, calc = sample_calc
    before = client.get(f"/api/calculations/{calc['id']}/verify", headers=guest).json()
    assert before["reproducible"]
    # admin publishes a new version of the India hotel factor
    new = {"factor_key": "accommodation.hotel.india", "category": "accommodation", "activity": "Hotel stay",
           "subcategory": "Hotel room-night - India (TEST)", "emission_factor": 40.0, "activity_unit": "room.night",
           "geography": "India", "reporting_year": "2026", "source_name": "Test source", "source_url": "https://example.org/test",
           "dataset_version": "TEST-2026", "system_boundary": "test", "methodology": "test"}
    assert client.post("/api/admin/factors", json=new, headers=guest).status_code == 403   # non-admin blocked
    r = client.post("/api/admin/factors", json=new, headers=admin)
    assert r.status_code == 200 and r.json()["is_active"]
    after = client.get(f"/api/calculations/{calc['id']}/verify", headers=guest).json()
    assert after["reproducible"]                                    # stored result still reproducible with pinned ids
    assert after["recomputed_with_current_factors_kg"] < after["stored_total_kg"]
    assert "accommodation.hotel.india" in after["factors_changed_since"]
    stored = client.get(f"/api/calculations/{calc['id']}", headers=guest).json()
    assert stored["result"]["total_kg"] == calc["result"]["total_kg"]   # stored result never changes
    # roll back to the official factor
    off = client.post("/api/admin/factors/accommodation.hotel.india@DESNZ-2026-v1.2/activate", headers=admin)
    assert off.status_code == 200
    assert client.post("/api/admin/factors", json=new, headers=admin).status_code == 409   # versions are immutable


def test_scenarios(client, guest, sample_calc):
    _, calc = sample_calc
    pres = client.get("/api/scenario-presets").json()
    assert {"shared_transport", "vegetarian_meals", "renewable_electricity", "virtual_attendance"} <= {p["preset"] for p in pres}
    s = client.post(f"/api/calculations/{calc['id']}/scenarios", json={"preset": "vegetarian_meals", "params": {"share_pct": 100}},
                    headers=guest).json()
    assert s["reduction_kg"] > 0 and s["scenario_kg"] < s["baseline_kg"]
    ren = client.post(f"/api/calculations/{calc['id']}/scenarios", json={"preset": "renewable_electricity"}, headers=guest).json()
    assert ren["reduction_kg"] == pytest.approx(0, abs=1e-6) and ren["market_reduction_kg"] > 0
    conf = client.get(f"/api/conferences/{calc['conference_id']}", headers=guest).json()["input"]
    conf["energy"]["diesel_generator_litres"] = 0
    c = client.post(f"/api/calculations/{calc['id']}/scenarios", json={"scenario_input": conf, "title": "No generator"},
                    headers=guest).json()
    assert c["reduction_kg"] > 0 and c["title"] == "No generator"


def test_recommendations_reflect_breakdown(sample_calc):
    _, calc = sample_calc
    recs = calc["recommendations"]
    assert recs and recs[0]["category"] == "transportation"     # transport dominates this sample
    assert all(r["evidence"] for r in recs)
    for r in recs:
        if r["potential_reduction_kg"]:
            assert r["potential_reduction_kg"] > 0


def test_csv_import(client, guest):
    csv = ("attendee_id,mode,origin,destination,distance_km,trip_type,passengers,occupancy,flight_class\n"
           "1,flight,DEL,BLR,,return,1,,economy\n"
           "2,Train,Chennai,Bengaluru,350,return,1,,\n"
           "2,Train,Chennai,Bengaluru,350,return,1,,\n"
           "3,spaceship,A,B,10,return,1,,\n"
           "4,car,Mysuru,Bengaluru,,return,2,2,\n"
           "5,flight,XXX,BLR,,return,1,,economy\n")
    r = client.post("/api/imports/transport", files={"file": ("t.csv", csv, "text/csv")}, headers=guest).json()
    assert r["total_rows"] == 6 and r["valid_rows"] == 2 and r["duplicates"] == 1 and r["invalid_rows"] == 3
    msgs = " ".join(e["message"] for e in r["errors"])
    assert "spaceship" in msgs and "Distance is missing" in msgs and "IATA" in msgs
    assert r["entries"][0]["distance_source"] == "estimated_airport"
    assert client.get("/api/imports/transport/template").status_code == 200


def test_reference_endpoints(client):
    opts = client.get("/api/meta/options").json()
    assert any(h["country"] == "India" for h in opts["hotel_countries"])
    assert "composting" in opts["waste_routes"]["food"]
    ap = client.get("/api/meta/airports", params={"q": "Bengaluru"}).json()
    assert any(a["iata"] == "BLR" for a in ap)
    d = client.get("/api/meta/distance", params={"origin": "DEL", "destination": "BOM"}).json()
    assert 1100 < d["distance_km"] < 1170 and d["source"] == "estimated_airport"
    f = client.get("/api/factors", params={"category": "energy"}).json()
    assert any(x["factor_key"] == "electricity.grid.IN" for x in f)
    assert len(client.get("/api/sources").json()) >= 15


def test_admin_endpoints_protected(client, guest, admin):
    assert client.get("/api/admin/stats", headers=guest).status_code == 403
    st = client.get("/api/admin/stats", headers=admin).json()
    assert st["factors_active"] > 200
    assert client.get("/api/admin/calculations", headers=admin).status_code == 200
