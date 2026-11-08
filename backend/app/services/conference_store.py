"""Persist a ConferenceInput into conferences + normalised entry tables (one transaction)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import (AccommodationEntry, Conference, ConferenceParticipant, EnergyEntry, FoodEntry, MaterialEntry,
                        TransportationEntry, WasteEntry)
from app.schemas.conference import ConferenceInput


def save(db: Session, conf: Conference, inp: ConferenceInput, step: int | None = None, transport_source: dict | None = None):
    b = inp.basic
    conf.name, conf.conference_type, conf.format = b.name, b.conference_type.value, b.format.value
    conf.country, conf.country_code, conf.state_city = b.country, b.country_code, b.state_city
    conf.venue_name, conf.venue_area_m2 = b.venue_name, b.venue_area_m2
    conf.start_date, conf.end_date, conf.days = b.start_date, b.end_date, b.days
    conf.input_json = inp.model_dump(mode="json")
    if step is not None:
        conf.current_step = step
    for rel in ("participants", "transport", "accommodation", "energy", "food", "waste", "materials"):
        getattr(conf, rel).clear()
    for g in ("attendees", "speakers", "organisers_staff", "volunteers", "virtual_attendees"):
        conf.participants.append(ConferenceParticipant(group=g, count=getattr(b, g)))
    src = transport_source or {}
    for e in inp.transport:
        conf.transport.append(TransportationEntry(
            entry_uid=e.id, data_type=e.data_type, data=e.model_dump(mode="json"), mode=e.mode.value, group=e.group,
            origin=e.origin, destination=e.destination, distance_km=e.distance_km, distance_source=e.distance_source,
            passengers=e.passengers, trip_type=e.trip_type, trips=e.trips, vehicle_type=e.vehicle_type,
            fuel_type=e.fuel_type, occupancy=e.occupancy, flight_class=e.flight_class, source=src.get(e.id, "form")))
    for a in inp.accommodation:
        conf.accommodation.append(AccommodationEntry(entry_uid=a.id, data_type=a.data_type, data=a.model_dump(mode="json"),
                                                     country=a.country, rooms=a.rooms, guests=a.guests, nights=a.nights))
    if inp.energy:
        en = inp.energy
        conf.energy.append(EnergyEntry(entry_uid="energy", data_type=en.data_type, data=en.model_dump(mode="json"),
                                       grid_electricity_kwh=en.grid_electricity_kwh,
                                       renewable_certified_kwh=en.renewable_certified_kwh,
                                       diesel_generator_litres=en.diesel_generator_litres))
    if inp.food:
        for m in inp.food.meals:
            conf.food.append(FoodEntry(entry_uid=m.id, data_type=m.data_type, data=m.model_dump(mode="json"), entry_type="meal",
                                       service=m.service, item=m.diet, quantity=m.count, unit="meal"))
        for i in inp.food.ingredients:
            conf.food.append(FoodEntry(entry_uid=i.id, data_type=i.data_type, data=i.model_dump(mode="json"),
                                       entry_type="ingredient", service=i.service, item=i.food_key, quantity=i.quantity, unit=i.unit))
        if inp.food.bottled_water:
            bw = inp.food.bottled_water
            conf.food.append(FoodEntry(entry_uid="bottled_water", data_type=bw.data_type, data=bw.model_dump(mode="json"),
                                       entry_type="bottled_water", service=None, item="bottled water", quantity=bw.bottles, unit="bottle"))
    if inp.waste:
        for w in inp.waste.entries:
            conf.waste.append(WasteEntry(entry_uid=w.id, data_type=w.data_type, data=w.model_dump(mode="json"),
                                         material=w.material, generated_kg=w.generated_kg))
    if inp.materials:
        for m in inp.materials.entries:
            conf.materials.append(MaterialEntry(entry_uid=m.id, data_type=m.data_type, data=m.model_dump(mode="json"),
                                                item=m.item, material_key=m.material_key, quantity=m.quantity, unit=m.unit))
    db.add(conf)
    db.commit()
    db.refresh(conf)
    return conf
