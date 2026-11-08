import pytest

from app.schemas.conference import ConferenceInput
from app.services import recommendations, scenarios
from app.services.emissions_engine import EmissionsEngine


def base_input():
    return ConferenceInput.model_validate({
        "basic": {"name": "S", "attendees": 200, "days": 1, "country_code": "IN"},
        "transport": [{"id": "cars", "mode": "car", "distance_km": 30, "passengers": 200, "occupancy": 1, "trip_type": "return",
                       "vehicle_type": "sedan", "fuel_type": "petrol", "group": "attendees"}],
        "energy": {"grid_electricity_kwh": 1000},
        "food": {"meals": [{"service": "lunch", "diet": "non_vegetarian_chicken", "count": 200}]},
    })


def test_scenario_a_vs_b_cars_vs_shared_buses(repo, F):
    """Spec example: 200 participants travel individually by car (A) vs shared buses (B)."""
    res = scenarios.run_scenario(base_input(), "shared_transport", {"share_pct": 100}, repo)
    a = 200 * 30 * 2 * F("transport.car.sedan.petrol.IN")
    b = 200 * 30 * 2 * F("transport.bus.coach.uk")
    assert res["reduction_kg"] == pytest.approx(a - b, rel=1e-6)
    assert res["reduction_pct"] == pytest.approx(100 * (a - b) / res["baseline_kg"], abs=0.01)


def test_vegetarian_scenario(repo, F):
    res = scenarios.run_scenario(base_input(), "vegetarian_meals", None, repo)
    assert res["reduction_kg"] == pytest.approx(200 * (F("food.meal.non_vegetarian_chicken") - F("food.meal.vegetarian")), rel=1e-6)


def test_renewable_only_changes_market_based(repo, F):
    res = scenarios.run_scenario(base_input(), "renewable_electricity", None, repo)
    assert res["reduction_kg"] == pytest.approx(0, abs=1e-9)
    assert res["market_reduction_kg"] == pytest.approx(1000 * F("electricity.grid.IN"), rel=1e-6)
    onsite = scenarios.run_scenario(base_input(), "renewable_electricity", {"mode": "onsite"}, repo)
    assert onsite["reduction_kg"] == pytest.approx(1000 * F("electricity.grid.IN"), rel=1e-6)


def test_virtual_attendance_scales_travel_and_meals(repo):
    res = scenarios.run_scenario(base_input(), "virtual_attendance", {"virtual_pct": 50}, repo)
    base = res["baseline_by_category"]
    sc = res["scenario_by_category"]
    assert sc["transportation"] == pytest.approx(base["transportation"] / 2, rel=1e-6)
    assert sc["food"] == pytest.approx(base["food"] / 2, rel=1e-6)
    assert sc["energy"] == pytest.approx(base["energy"])       # venue kept (conservative)


def test_scenarios_do_not_mutate_baseline(repo):
    inp = base_input()
    before = inp.model_dump()
    scenarios.run_all(inp, repo)
    assert inp.model_dump() == before


def test_recommendations_follow_breakdown(repo):
    inp = base_input()
    r = EmissionsEngine(repo).calculate(inp)
    recs = recommendations.generate(r, scenarios.run_all(inp, repo))
    cats = [x["category"] for x in recs]
    assert "transportation" in cats and "food" in cats
    assert "materials" not in cats and "waste" not in cats      # no data -> no generic advice
    assert recs[0]["potential_reduction_kg"] == max(x["potential_reduction_kg"] or 0 for x in recs)
