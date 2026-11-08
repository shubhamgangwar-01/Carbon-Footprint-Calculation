"""Three documented sample conferences. Each expected total is computed here by an
independent, line-by-line hand calculation (formulas written out explicitly, factor
values read from the processed factor database) and compared with the engine.
The resulting reference totals are also documented in docs/sample_scenarios.md."""
import pytest

from app.calculations.geo import flight_distance_km
from app.calculations.units import pages_to_paper_kg
from app.schemas.conference import ConferenceInput
from app.services.emissions_engine import EmissionsEngine
from tests.conftest import load_sample

# Reference totals (kg CO2e) from the hand calculations below, factor set FS-2026.1.
REFERENCE_TOTALS = {"small_academic_100": 7456.244, "medium_corporate_500": 111783.290, "large_international_2000": 1511540.428}


def gcd(a, b):
    return flight_distance_km(a, b)[0]


def hand_small(F):
    t = {}
    t["flight DEL-BLR"] = 10 * 1700 * 2 * F("transport.flight.short_haul_uk.economy.with_rf")
    t["train Chennai"] = 30 * 350 * 2 * F("transport.rail.national.IN")
    t["city bus"] = 40 * 15 * 2 * 2 * F("transport.bus.city.IN")
    t["car pool"] = (10 / 2) * 25 * 2 * 2 * F("transport.car.hatchback.petrol.IN")
    t["hotel"] = 10 * 2 * F("accommodation.hotel.india")
    t["grid"] = 1800 * F("electricity.grid.IN")
    t["generator"] = 40 * F("energy.fuel.diesel.litre")
    t["meals"] = 150 * F("food.meal.vegetarian") + 50 * F("food.meal.non_vegetarian_chicken") + 400 * F("food.meal.snack_refreshment")
    t["bottles"] = 200 * 0.010 * F("materials.plastic.pet") + 200 * 0.5 / 1000 * F("water.supply")
    t["waste"] = (25 * F("waste.food.composting") + 15 * F("waste.food.landfill") + 10 * F("waste.paper.recycling")
                  + 5 * F("waste.paper.landfill") + 8 * F("waste.plastic.landfill"))
    t["materials"] = (pages_to_paper_kg(800, 80, "A4", True) * F("materials.paper.virgin") + 3 * F("materials.plastic.pvc")
                      + 100 * 0.012 * F("materials.plastic.pet"))
    return t


def hand_medium(F):
    sh = F("transport.flight.short_haul_uk.economy.with_rf")
    t = {}
    t["DEL-BOM"] = 120 * gcd("DEL", "BOM") * 2 * sh
    t["BLR-BOM"] = 80 * gcd("BLR", "BOM") * 2 * sh
    t["SIN-BOM"] = 5 * gcd("SIN", "BOM") * 2 * F("transport.flight.international_non_uk.business.with_rf")
    t["LHR-BOM"] = 4 * gcd("LHR", "BOM") * 2 * F("transport.flight.long_haul_uk.economy.with_rf")
    t["train Pune"] = 60 * 190 * 2 * F("transport.rail.national.IN")
    t["suburban"] = 100 * 20 * 2 * 2 * F("transport.rail.suburban.IN")
    t["taxi"] = (209 / 1.5) * 18 * 2 * F("transport.car.small.cng.IN")
    t["cars"] = (80 / 1.2) * 22 * 2 * 2 * F("transport.car.suv.diesel.IN")
    t["hotel"] = 230 * 2 * F("accommodation.hotel.india")
    t["energy"] = 9500 * F("electricity.grid.IN") + 150 * F("energy.fuel.diesel.litre") + 120 * F("energy.fuel.lpg.tonne") / 1000
    t["meals"] = ((460 + 550 + 250) * F("food.meal.vegetarian") + 350 * F("food.meal.non_vegetarian_chicken")
                  + 100 * F("food.meal.non_vegetarian_fish") + 200 * F("food.meal.non_vegetarian_mutton")
                  + 2000 * F("food.meal.snack_refreshment_coffee"))
    t["bottles"] = 1500 * 0.010 * F("materials.plastic.pet") + 1500 * 0.5 / 1000 * F("water.supply")
    t["waste"] = (200 * F("waste.food.landfill") + 60 * F("waste.food.composting") + 70 * F("waste.cardboard.recycling")
                  + 10 * F("waste.cardboard.landfill") + 20 * F("waste.plastic.recycling") + 40 * F("waste.plastic.landfill")
                  + 120 * F("waste.mixed.landfill"))
    t["materials"] = (pages_to_paper_kg(12000, 130, "A4", True) * F("materials.paper.virgin") + (40 + 500 * 0.005) * F("materials.plastic.pvc")
                      + 500 * 0.012 * F("materials.plastic.pet") + 500 * 0.090 * F("materials.textile.clothing"))
    return t


def hand_large(F):
    sh = F("transport.flight.short_haul_uk.economy.with_rf")
    intl = F("transport.flight.international_non_uk.economy.with_rf")
    t = {}
    t["LHR"] = 150 * gcd("LHR", "DEL") * 2 * F("transport.flight.long_haul_uk.economy.with_rf")
    t["JFK"] = 120 * gcd("JFK", "DEL") * 2 * intl
    t["SIN"] = 100 * gcd("SIN", "DEL") * 2 * intl            # 4,100 km > 3,700 km
    t["DXB"] = 80 * gcd("DXB", "DEL") * 2 * sh               # 2,190 km
    t["NRT"] = 60 * gcd("NRT", "DEL") * 2 * intl
    t["FRA"] = 40 * gcd("FRA", "DEL") * 2 * F("transport.flight.international_non_uk.business.with_rf")
    t["BOM"] = 300 * gcd("BOM", "DEL") * 2 * sh
    t["BLR"] = 250 * gcd("BLR", "DEL") * 2 * sh
    t["CCU"] = 150 * gcd("CCU", "DEL") * 2 * sh
    t["train"] = 300 * 400 * 2 * F("transport.rail.national.IN")
    t["metro"] = 800 * 12 * 2 * 4 * F("transport.rail.light_rail_tram")
    t["coach"] = 700 * 15 * 2 * 4 * F("transport.bus.coach.uk")
    t["taxi"] = (1250 / 2) * 20 * 2 * F("transport.car.small.cng.IN")
    t["ev"] = (40 / 2) * 20 * 2 * 4 * F("transport.car.medium.bev.IN")
    t["hotels"] = 1100 * 4 * F("accommodation.hotel.india") + 100 * 4 * 25.0
    t["energy"] = 64000 * F("electricity.grid.IN") + 1500 * F("energy.fuel.diesel.litre") + 900 * F("energy.fuel.lpg.tonne") / 1000
    t["meals"] = ((4400 + 4000 + 1500) * F("food.meal.vegetarian") + 800 * F("food.meal.vegan")
                  + (3200 + 1200) * F("food.meal.non_vegetarian_chicken") + 300 * F("food.meal.non_vegetarian_fish")
                  + 16000 * F("food.meal.snack_refreshment"))
    t["waste"] = (1200 * F("waste.food.composting") + 400 * F("waste.food.anaerobic_digestion") + 800 * F("waste.food.landfill")
                  + 400 * F("waste.paper.recycling") + 100 * F("waste.paper.landfill") + 550 * F("waste.cardboard.recycling")
                  + 50 * F("waste.cardboard.landfill") + 250 * F("waste.plastic.recycling") + 50 * F("waste.plastic.incineration")
                  + 150 * F("waste.plastic.landfill") + 120 * F("waste.glass.recycling") + 60 * F("waste.metal.recycling")
                  + 900 * F("waste.mixed.landfill"))
    t["materials"] = (pages_to_paper_kg(120000, 70, "A4", True) * F("materials.paper.recycled")
                      + 60 * F("materials.textile.clothing") / 5 + 150 * F("materials.plastic.pvc")
                      + 2000 * 0.008 * F("materials.board.recycled") + 2000 * 0.012 * F("materials.plastic.pet")
                      + 2000 * 0.090 * F("materials.textile.clothing"))
    return t


HAND = {"small_academic_100": hand_small, "medium_corporate_500": hand_medium, "large_international_2000": hand_large}


@pytest.mark.parametrize("name", list(HAND))
def test_sample_matches_hand_calculation(name, repo, F):
    result = EmissionsEngine(repo).calculate(ConferenceInput.model_validate(load_sample(name)))
    hand = HAND[name](F)
    expected = sum(hand.values())
    assert result.total_kg == pytest.approx(expected, rel=1e-6), {k: round(v, 2) for k, v in hand.items()}
    assert result.completeness["is_complete"], result.issues
    # regression guard: documented reference total (docs/sample_scenarios.md) for factor set FS-2026.1
    assert result.total_kg == pytest.approx(REFERENCE_TOTALS[name], abs=0.01)
    # no category counted twice: each input entry id appears in lines of exactly one category
    cats_by_entry = {}
    for l in result.lines:
        if l.entry_ref:
            cats_by_entry.setdefault(l.entry_ref, set()).add(l.category)
    assert all(len(v) == 1 for v in cats_by_entry.values())


def test_sample_large_offsets_and_market_based(repo, F):
    r = EmissionsEngine(repo).calculate(ConferenceInput.model_validate(load_sample("large_international_2000")))
    assert r.offsets_tonnes == 100
    assert r.net_tonnes_after_offsets == pytest.approx(r.total_tonnes - 100)
    assert r.location_based_electricity_kg - r.market_based_electricity_kg == pytest.approx(19200 * F("electricity.grid.IN"))
    assert r.participants == 2000 and r.days == 4
