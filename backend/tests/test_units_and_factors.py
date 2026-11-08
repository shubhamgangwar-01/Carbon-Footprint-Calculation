import json
import math

import pytest

from app.calculations import units
from app.calculations.factor_repository import FactorNotFound, FactorRepository
from app.calculations.geo import flight_distance_km, haversine_km
from tests.conftest import FACTORS_JSON


def test_distance_conversion():
    assert units.to_km(100, "miles") == pytest.approx(160.9344)
    assert units.to_km(5, "km") == 5


def test_mass_volume_energy_conversion():
    assert units.to_kg(2, "tonne") == 2000
    assert units.to_kg(500, "g") == 0.5
    assert units.to_kg(1, "lb") == pytest.approx(0.45359237)
    assert units.to_litres(1, "us_gallon") == pytest.approx(3.785411784)
    assert units.to_kwh(1, "gj") == pytest.approx(277.7777778)
    assert units.to_kwh(2, "mwh") == 2000


def test_unknown_unit_raises():
    with pytest.raises(units.UnitError):
        units.to_kg(1, "stone")


def test_pages_to_paper_mass():
    # 1000 A4 pages, 80 gsm, single-sided: 1000 x 0.21 x 0.297 m2 x 80 g = 4989.6 g
    assert units.pages_to_paper_kg(1000, 80, "A4") == pytest.approx(4.9896)
    assert units.pages_to_paper_kg(1000, 80, "A4", double_sided=True) == pytest.approx(2.4948)


def test_haversine_known_distance():
    # London Heathrow - New Delhi: published great-circle ~6,700 km
    d, a, b = flight_distance_km("LHR", "DEL")
    assert 6650 < d < 6800
    assert a["country"] == "GB" and b["country"] == "IN"
    assert haversine_km(0, 0, 0, 1) == pytest.approx(111.195, rel=1e-3)


def test_every_factor_has_source_and_boundary(repo):
    for f in repo.all():
        assert f.source_name and f.source_url, f.factor_id
        assert f.system_boundary, f.factor_id
        assert math.isfinite(f.value) and f.value >= 0, f.factor_id
        assert f.unit.startswith(("kg CO2e/", "kg CO2/", "kWh/")), f.factor_id


def test_india_grid_factor_matches_cea(F):
    assert F("electricity.grid.IN.co2") == pytest.approx(0.675)
    # CO2e = CO2 x IPCC coal CH4/N2O ratio
    assert F("electricity.grid.IN") == pytest.approx(0.675 * (94600 + 28 + 1.5 * 265) / 94600)


def test_two_active_versions_rejected():
    db = json.loads(FACTORS_JSON.read_text())
    recs = db["factors"]
    dup = dict(next(r for r in recs if r["factor_key"] == "electricity.grid.GB"))
    dup["factor_id"] = "electricity.grid.GB@TEST"
    with pytest.raises(ValueError, match="Two active factors"):
        FactorRepository(recs + [dup])


def test_inactive_previous_version_retained(repo):
    old = repo.by_id("transport.bus.coach.uk@DESNZ-2025")
    new = repo.get("transport.bus.coach.uk")
    assert not old.is_active and new.is_active
    assert new.dataset_version == "DESNZ-2026-v1.2"


def test_pinned_factor_lookup(repo):
    f = repo.get("transport.bus.coach.uk", pinned={"transport.bus.coach.uk": "transport.bus.coach.uk@DESNZ-2025"})
    assert f.dataset_version == "DESNZ-2025"
    with pytest.raises(FactorNotFound):
        repo.get("does.not.exist")
