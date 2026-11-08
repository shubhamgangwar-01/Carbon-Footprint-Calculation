import pytest
from pydantic import ValidationError

from app.schemas.conference import ConferenceInput, EnergyData, FoodData, MaterialEntry, WasteEntry


# ------------------------------------------------------------------ electricity / energy
def test_electricity_location_and_market_based(calc, F):
    r = calc({"energy": {"grid_electricity_kwh": 10000, "renewable_certified_kwh": 4000}})
    g = F("electricity.grid.IN")
    assert r.total_kg == pytest.approx(10000 * g)                     # headline = location-based
    assert r.location_based_electricity_kg == pytest.approx(10000 * g)
    assert r.market_based_electricity_kg == pytest.approx(6000 * g)
    assert r.total_market_based_kg == pytest.approx(6000 * g)


def test_metered_electricity_suppresses_estimates(calc, F):
    r = calc({"energy": {"grid_electricity_kwh": 1000, "ac_power_kw": 50, "ac_hours_per_day": 8,
                         "equipment": [{"name": "LED wall", "power_kw": 5, "hours_per_day": 8}]}})
    assert r.total_kg == pytest.approx(1000 * F("electricity.grid.IN"))
    assert any("ignored to avoid double counting" in i.message for i in r.issues)


def test_estimated_electricity_from_loads(calc, F):
    r = calc({"basic": {"days": 3}, "energy": {"ac_power_kw": 40, "ac_hours_per_day": 9, "lighting_power_kw": 5,
                                               "lighting_hours_per_day": 10,
                                               "equipment": [{"name": "Projectors", "power_kw": 0.4, "quantity": 5, "hours_per_day": 8}]}})
    kwh = 40 * 9 * 3 + 5 * 10 * 3 + 0.4 * 5 * 8 * 3
    l = r.lines[0]
    assert l.quantity == pytest.approx(kwh) and l.data_type == "estimated"
    assert r.total_kg == pytest.approx(kwh * F("electricity.grid.IN"))


def test_generator_and_lpg(calc, F):
    r = calc({"energy": {"grid_electricity_kwh": 0, "diesel_generator_litres": 200, "lpg_kg": 50}})
    assert r.total_kg == pytest.approx(200 * F("energy.fuel.diesel.litre") + 50 * F("energy.fuel.lpg.tonne") / 1000)


def test_historical_grid_year(calc, F):
    r = calc({"settings": {"grid_reporting_year": "2023-24"}, "energy": {"grid_electricity_kwh": 1000}})
    assert r.total_kg == pytest.approx(1000 * F("electricity.grid.IN.FY2023-24"))


def test_country_without_grid_factor_requires_supplier_factor(calc):
    r = calc({"basic": {"country_code": "DE", "country": "Germany"}, "energy": {"grid_electricity_kwh": 1000}})
    assert r.total_kg == 0 and any(i.level == "error" for i in r.issues)
    r2 = calc({"basic": {"country_code": "DE", "country": "Germany"},
               "energy": {"grid_electricity_kwh": 1000, "supplier_factor_kg_per_kwh": 0.4}})
    assert r2.total_kg == pytest.approx(400)


def test_renewable_cannot_exceed_total():
    with pytest.raises(ValidationError):
        EnergyData(grid_electricity_kwh=100, renewable_certified_kwh=200)


def test_no_electricity_data_flagged(calc):
    r = calc({"energy": {"diesel_generator_litres": 10}})
    assert next(c for c in r.by_category if c.category == "energy").status == "incomplete"


# ------------------------------------------------------------------ accommodation
def test_accommodation_rooms(calc, F):
    r = calc({"accommodation": [{"country": "India", "rooms": 50, "nights": 3}]})
    assert r.total_kg == pytest.approx(150 * F("accommodation.hotel.india"))


def test_accommodation_guests_per_room(calc, F):
    r = calc({"accommodation": [{"country": "India", "guests": 60, "guests_per_room": 2, "nights": 2}]})
    assert r.total_kg == pytest.approx(30 * 2 * F("accommodation.hotel.india"))
    r2 = calc({"accommodation": [{"country": "India", "guests": 60, "nights": 2}]})
    assert r2.total_kg == pytest.approx(60 * 2 * F("accommodation.hotel.india"))
    assert r2.lines[0].data_type == "default"


def test_accommodation_hotel_specific_and_actual_energy(calc, F):
    r = calc({"accommodation": [{"country": "India", "rooms": 10, "nights": 2, "hotel_factor_kg_per_room_night": 20}]})
    assert r.total_kg == pytest.approx(400)
    r2 = calc({"accommodation": [{"country": "India", "rooms": 10, "nights": 2, "electricity_kwh": 500, "diesel_litres": 10}]})
    assert r2.total_kg == pytest.approx(500 * F("electricity.grid.IN") + 10 * F("energy.fuel.diesel.litre"))


def test_accommodation_country_alias_and_unknown(calc, F):
    r = calc({"accommodation": [{"country": "UK", "rooms": 1, "nights": 1}]})
    assert r.total_kg == pytest.approx(F("accommodation.hotel.uk"))
    bad = calc({"accommodation": [{"country": "Atlantis", "rooms": 1, "nights": 1}]})
    assert bad.total_kg == 0 and any("No published hotel factor" in i.message for i in bad.issues)


# ------------------------------------------------------------------ food
def test_meals(calc, F):
    r = calc({"food": {"meals": [{"service": "lunch", "diet": "vegetarian", "count": 100},
                                 {"service": "lunch", "diet": "non_vegetarian_chicken", "count": 50}]}})
    assert r.total_kg == pytest.approx(100 * F("food.meal.vegetarian") + 50 * F("food.meal.non_vegetarian_chicken"))
    assert F("food.meal.vegan") < F("food.meal.vegetarian") < F("food.meal.non_vegetarian_chicken") < F("food.meal.non_vegetarian_beef")


def test_meal_model_is_sum_of_components(repo):
    f = repo.get("food.meal.vegetarian")
    comps = f.raw["derivation"]["components"]
    assert sum(c["grams"] / 1000 * repo.get(c["factor_key"]).value for c in comps) == pytest.approx(f.value, abs=1e-3)


def test_ingredients_and_units(calc, F):
    r = calc({"food": {"ingredients": [{"service": "lunch", "food_key": "food.rice", "quantity": 50, "unit": "kg"},
                                       {"service": "dinner", "food_key": "food.chicken", "quantity": 20000, "unit": "g"},
                                       {"service": "beverages", "food_key": "food.milk", "quantity": 30, "unit": "litre"}]}})
    assert r.total_kg == pytest.approx(50 * F("food.rice") + 20 * F("food.chicken") + 30 * F("food.milk"))


def test_meal_and_ingredient_same_service_rejected():
    with pytest.raises(ValidationError, match="double counting"):
        FoodData(meals=[{"service": "lunch", "diet": "vegetarian", "count": 10}],
                 ingredients=[{"service": "lunch", "food_key": "food.rice", "quantity": 5}])
    FoodData(meals=[{"service": "lunch", "diet": "vegetarian", "count": 10}],
             ingredients=[{"service": "beverages", "food_key": "food.coffee", "quantity": 1}])


def test_bottled_water_requires_mass(calc, F):
    r = calc({"food": {"bottled_water": {"bottles": 100}}})
    assert r.total_kg == 0 and any("PET mass" in i.message for i in r.issues)
    r2 = calc({"food": {"bottled_water": {"bottles": 100, "bottle_mass_g": 10, "volume_litres": 0.5}}})
    assert r2.total_kg == pytest.approx(1.0 * F("materials.plastic.pet") + 0.05 * F("water.supply"))


# ------------------------------------------------------------------ waste
def test_waste_routes(calc, F):
    r = calc({"waste": {"entries": [{"material": "food", "generated_kg": 100, "landfill_kg": 60, "composting_kg": 40},
                                    {"material": "plastic", "generated_kg": 10, "recycling_kg": 10}]}})
    exp = 60 * F("waste.food.landfill") + 40 * F("waste.food.composting") + 10 * F("waste.plastic.recycling")
    assert r.total_kg == pytest.approx(exp)


def test_waste_unassigned_goes_to_landfill_flagged(calc, F):
    r = calc({"waste": {"entries": [{"material": "mixed", "generated_kg": 50, "landfill_kg": 20}]}})
    assert r.total_kg == pytest.approx(50 * F("waste.mixed.landfill"))
    assert any(l.data_type == "default" for l in r.lines)


def test_waste_routes_cannot_exceed_generated():
    with pytest.raises(ValidationError, match="exceeds waste generated"):
        WasteEntry(material="paper", generated_kg=10, recycling_kg=8, landfill_kg=5)


def test_invalid_route_reported(calc):
    r = calc({"waste": {"entries": [{"material": "plastic", "generated_kg": 10, "composting_kg": 10}]}})
    assert any(i.level == "error" and "composting" in i.message for i in r.issues)


# ------------------------------------------------------------------ materials
def test_materials_pages_items_kg(calc, F):
    r = calc({"materials": {"entries": [
        {"item": "Programmes", "material_key": "materials.paper.virgin", "quantity": 1000, "unit": "pages", "paper_gsm": 80},
        {"item": "ID cards", "material_key": "materials.plastic.pvc", "quantity": 200, "unit": "items", "unit_mass_g": 5},
        {"item": "Banner", "material_key": "materials.plastic.pvc", "quantity": 2, "unit": "kg"}]}})
    exp = 4.9896 * F("materials.paper.virgin") + (1.0 + 2) * F("materials.plastic.pvc")
    assert r.total_kg == pytest.approx(exp)


def test_reusable_items_amortised(calc, F):
    r = calc({"materials": {"entries": [{"item": "Fabric banner", "material_key": "materials.textile.clothing", "quantity": 10,
                                         "unit": "kg", "reusable": True, "expected_uses": 5}]}})
    assert r.total_kg == pytest.approx(10 * F("materials.textile.clothing") / 5)


def test_items_require_mass():
    with pytest.raises(ValidationError, match="mass per item"):
        MaterialEntry(item="Lanyards", material_key="materials.plastic.pet", quantity=10, unit="items")


# ------------------------------------------------------------------ totals & completeness
def test_total_is_sum_of_lines_and_categories(calc):
    from tests.conftest import load_sample
    from app.services.emissions_engine import EmissionsEngine
    r = calc({"transport": [{"mode": "train", "distance_km": 100, "passengers": 10}],
              "energy": {"grid_electricity_kwh": 500}, "accommodation": [{"country": "India", "rooms": 5, "nights": 1}]})
    assert r.total_kg == pytest.approx(sum(l.emissions_kg for l in r.lines), abs=1e-3)
    assert r.total_kg == pytest.approx(sum(c.emissions_kg for c in r.by_category), abs=1e-2)
    assert sum(c.share_pct for c in r.by_category) == pytest.approx(100, abs=0.05)


def test_not_reported_vs_not_applicable(calc):
    r = calc({"transport": [{"mode": "train", "distance_km": 100, "passengers": 1}], "accommodation_not_applicable": True})
    st = {c.category: c.status for c in r.by_category}
    assert st["accommodation"] == "not_applicable"
    assert st["food"] == "not_reported"
    assert "food" in r.completeness["categories_not_reported"]


def test_per_participant_and_day(calc):
    r = calc({"basic": {"attendees": 80, "speakers": 10, "organisers_staff": 5, "volunteers": 5, "days": 4},
              "energy": {"grid_electricity_kwh": 1000}})
    assert r.participants == 100
    assert r.per_participant_kg == pytest.approx(r.total_kg / 100, abs=1e-3)
    assert r.per_day_kg == pytest.approx(r.total_kg / 4, abs=1e-3)


def test_offsets_reported_separately(calc):
    r = calc({"energy": {"grid_electricity_kwh": 10000}, "offsets": {"tonnes_co2e": 2}})
    assert r.total_tonnes == pytest.approx(10000 * 0.678 / 1000, rel=1e-3)   # gross unchanged
    assert r.net_tonnes_after_offsets == pytest.approx(r.total_tonnes - 2)


def test_invalid_dates_rejected():
    with pytest.raises(ValidationError):
        ConferenceInput.model_validate({"basic": {"name": "x", "attendees": 1, "start_date": "2026-05-03", "end_date": "2026-05-01"}})
    with pytest.raises(ValidationError):
        ConferenceInput.model_validate({"basic": {"name": "x", "attendees": 1}})  # no days
