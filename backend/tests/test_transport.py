import pytest
from pydantic import ValidationError

from app.calculations.geo import flight_distance_km


def tline(r):
    return [l for l in r.lines if l.category == "transportation"]


def test_return_journey_doubles_distance(calc, F):
    one = calc({"transport": [{"mode": "train", "distance_km": 300, "passengers": 10, "trip_type": "one_way"}]})
    ret = calc({"transport": [{"mode": "train", "distance_km": 300, "passengers": 10, "trip_type": "return"}]})
    assert one.total_kg == pytest.approx(10 * 300 * F("transport.rail.national.IN"))
    assert ret.total_kg == pytest.approx(2 * one.total_kg)


def test_trips_multiply(calc, F):
    r = calc({"transport": [{"mode": "bus", "distance_km": 10, "passengers": 50, "trip_type": "return", "trips": 3, "vehicle_type": "city"}]})
    assert r.total_kg == pytest.approx(50 * 10 * 2 * 3 * F("transport.bus.city.IN"))


def test_vehicle_occupancy_applied_once(calc, F):
    # 12 people, 3 per car => 4 cars; emissions per vehicle-km, NOT per passenger
    r = calc({"transport": [{"mode": "car", "distance_km": 50, "passengers": 12, "occupancy": 3, "trip_type": "one_way",
                             "vehicle_type": "sedan", "fuel_type": "diesel"}]})
    l = tline(r)[0]
    assert l.quantity == pytest.approx(4 * 50)
    assert l.quantity_unit == "vehicle.km"
    assert r.total_kg == pytest.approx(200 * F("transport.car.sedan.diesel.IN"))


def test_vehicle_count_overrides_occupancy(calc, F):
    r = calc({"transport": [{"mode": "car", "distance_km": 50, "passengers": 12, "vehicles": 2, "occupancy": 3, "trip_type": "one_way",
                             "vehicle_type": "suv", "fuel_type": "petrol"}]})
    assert r.total_kg == pytest.approx(2 * 50 * F("transport.car.suv.petrol.IN"))


def test_missing_occupancy_is_conservative_default(calc, F):
    r = calc({"transport": [{"mode": "taxi", "distance_km": 10, "passengers": 4, "trip_type": "one_way", "fuel_type": "cng"}]})
    l = tline(r)[0]
    assert l.data_type == "default"
    assert r.total_kg == pytest.approx(4 * 10 * F("transport.car.small.cng.IN"))


def test_flight_short_haul_non_uk_with_and_without_rf(calc, F):
    d, _, _ = flight_distance_km("DEL", "BOM")
    rf = calc({"transport": [{"mode": "flight", "origin": "DEL", "destination": "BOM", "passengers": 2, "trip_type": "return"}]})
    no = calc({"settings": {"include_radiative_forcing": False},
               "transport": [{"mode": "flight", "origin": "DEL", "destination": "BOM", "passengers": 2, "trip_type": "return"}]})
    assert rf.total_kg == pytest.approx(2 * d * 2 * F("transport.flight.short_haul_uk.economy.with_rf"))
    assert no.total_kg == pytest.approx(2 * d * 2 * F("transport.flight.short_haul_uk.economy.without_rf"))
    assert rf.total_kg > no.total_kg
    assert tline(rf)[0].data_type == "estimated"  # distance derived from airport coordinates


def test_flight_long_haul_bands(calc, F):
    uk = calc({"transport": [{"mode": "flight", "origin": "LHR", "destination": "DEL", "passengers": 1, "trip_type": "one_way",
                              "flight_class": "business"}]})
    assert tline(uk)[0].factor_id.startswith("transport.flight.long_haul_uk.business.with_rf")
    us = calc({"transport": [{"mode": "flight", "origin": "JFK", "destination": "DEL", "passengers": 1, "trip_type": "one_way"}]})
    assert tline(us)[0].factor_id.startswith("transport.flight.international_non_uk.economy.with_rf")
    dom = calc({"transport": [{"mode": "flight", "origin": "LHR", "destination": "EDI", "passengers": 1, "trip_type": "one_way"}]})
    assert tline(dom)[0].factor_id.startswith("transport.flight.domestic_uk.average.with_rf")


def test_short_haul_premium_class_maps_conservatively(calc):
    r = calc({"transport": [{"mode": "flight", "distance_km": 1200, "passengers": 1, "flight_class": "first", "trip_type": "one_way"}]})
    assert tline(r)[0].factor_id.startswith("transport.flight.short_haul_uk.business")


def test_manual_flight_distance_used(calc, F):
    r = calc({"transport": [{"mode": "flight", "distance_km": 5000, "passengers": 3, "flight_class": "economy", "trip_type": "one_way"}]})
    assert r.total_kg == pytest.approx(3 * 5000 * F("transport.flight.international_non_uk.economy.with_rf"))
    assert tline(r)[0].data_type == "actual"


def test_miles_converted(calc, F):
    r = calc({"transport": [{"mode": "train", "distance_km": 100, "distance_unit": "miles", "passengers": 1, "trip_type": "one_way"}]})
    assert r.total_kg == pytest.approx(160.9344 * F("transport.rail.national.IN"))


def test_missing_distance_not_treated_as_zero(calc):
    r = calc({"transport": [{"mode": "car", "passengers": 3, "occupancy": 3}]})
    assert r.total_kg == 0
    assert any(i.level == "error" and "NOT counted" in i.message for i in r.issues)
    cat = next(c for c in r.by_category if c.category == "transportation")
    assert cat.status == "incomplete"
    assert not r.completeness["is_complete"]


def test_india_vs_uk_factor_selection(calc, F):
    ind = calc({"transport": [{"mode": "train", "distance_km": 100, "passengers": 1, "trip_type": "one_way"}]})
    uk = calc({"basic": {"country_code": "GB", "country": "United Kingdom"},
               "transport": [{"mode": "train", "distance_km": 100, "passengers": 1, "trip_type": "one_way"}]})
    assert ind.total_kg == pytest.approx(100 * F("transport.rail.national.IN"))
    assert uk.total_kg == pytest.approx(100 * F("transport.rail.national.uk"))
    other = calc({"basic": {"country_code": "DE", "country": "Germany"},
                  "transport": [{"mode": "train", "distance_km": 100, "passengers": 1, "trip_type": "one_way"}]})
    assert tline(other)[0].is_proxy


def test_metro_and_coach_proxies_flagged(calc, F):
    r = calc({"transport": [{"mode": "train", "vehicle_type": "metro", "distance_km": 10, "passengers": 1, "trip_type": "one_way"},
                            {"mode": "bus", "vehicle_type": "coach", "distance_km": 10, "passengers": 1, "trip_type": "one_way"}]})
    ls = tline(r)
    assert all(l.is_proxy for l in ls)
    assert r.total_kg == pytest.approx(10 * F("transport.rail.light_rail_tram") + 10 * F("transport.bus.coach.uk"))


def test_electric_vehicle_uses_indian_grid(calc, F):
    r = calc({"transport": [{"mode": "electric_vehicle", "distance_km": 100, "passengers": 1, "occupancy": 1, "trip_type": "one_way",
                             "vehicle_type": "sedan"}]})
    assert r.total_kg == pytest.approx(100 * F("param.ev_kwh_per_km.medium") * F("electricity.grid.IN"))


def test_motorcycle_and_autorickshaw(calc, F):
    r = calc({"transport": [{"mode": "motorcycle", "vehicle_type": "scooter", "distance_km": 10, "passengers": 1, "occupancy": 1, "trip_type": "one_way"},
                            {"mode": "autorickshaw", "fuel_type": "cng", "distance_km": 10, "passengers": 2, "occupancy": 2, "trip_type": "one_way"}]})
    assert r.total_kg == pytest.approx(10 * F("transport.motorbike.scooter.IN") + 10 * F("transport.autorickshaw.cng.IN"))


def test_fuel_based_method_overrides_distance(calc, F):
    r = calc({"transport": [{"mode": "bus", "fuel_litres": 100, "fuel_type": "diesel", "distance_km": 9999, "passengers": 40}]})
    assert r.total_kg == pytest.approx(100 * F("energy.fuel.diesel.litre"))


def test_custom_factor(calc):
    r = calc({"transport": [{"mode": "other", "distance_km": 100, "passengers": 5, "trip_type": "return", "custom_factor": 0.05,
                             "custom_factor_unit": "passenger.km", "custom_factor_source": "operator data"}]})
    assert r.total_kg == pytest.approx(5 * 100 * 2 * 0.05)


def test_other_mode_requires_factor():
    from app.schemas.conference import TransportEntry
    with pytest.raises(ValidationError):
        TransportEntry(mode="other", distance_km=10)


def test_negative_values_rejected():
    from app.schemas.conference import TransportEntry
    with pytest.raises(ValidationError):
        TransportEntry(mode="car", distance_km=-5)
