"""Pydantic schemas describing a conference's activity data.

These schemas are the contract between the frontend forms, the CSV/Excel
importer, the database and the emissions engine. Every module is optional:
a module that is absent is reported as *not reported* (never silently zero),
while a module explicitly marked `not_applicable=True` is reported as zero with
that declaration recorded.
"""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

DataType = Literal["actual", "estimated", "default"]


def _id() -> str:
    return uuid4().hex[:10]


# ------------------------------------------------------------------ basic info
class ConferenceType(str, Enum):
    academic = "academic"
    corporate = "corporate"
    government = "government"
    exhibition = "exhibition"
    other = "other"


class ConferenceFormat(str, Enum):
    offline = "offline"
    online = "online"
    hybrid = "hybrid"


class BasicInfo(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    country: str = Field(default="India", description="Country where the conference is held")
    country_code: str = Field(default="IN", min_length=2, max_length=2, description="ISO 3166-1 alpha-2")
    state_city: Optional[str] = None
    location: Optional[str] = None
    venue_name: Optional[str] = None
    venue_area_m2: Optional[float] = Field(default=None, ge=0)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    days: Optional[int] = Field(default=None, ge=1, le=60)
    attendees: int = Field(ge=0, description="In-person delegates, excluding speakers, staff and volunteers")
    speakers: int = Field(default=0, ge=0)
    organisers_staff: int = Field(default=0, ge=0)
    volunteers: int = Field(default=0, ge=0)
    virtual_attendees: int = Field(default=0, ge=0)
    conference_type: ConferenceType = ConferenceType.academic
    format: ConferenceFormat = ConferenceFormat.offline

    @model_validator(mode="after")
    def _dates(self):
        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                raise ValueError("End date must be on or after the start date")
            span = (self.end_date - self.start_date).days + 1
            if self.days is None:
                self.days = span
            elif self.days > span:
                raise ValueError(f"Number of days ({self.days}) exceeds the date range ({span} days)")
        if self.days is None:
            raise ValueError("Provide either start and end dates or the number of conference days")
        self.country_code = self.country_code.upper()
        return self

    @property
    def total_participants(self) -> int:
        return self.attendees + self.speakers + self.organisers_staff + self.volunteers


# ------------------------------------------------------------------ settings
class CalculationSettings(BaseModel):
    include_radiative_forcing: bool = Field(default=True, description="Apply DESNZ RF uplift to flights (recommended)")
    grid_reporting_year: Optional[str] = Field(default=None, description="e.g. '2024-25' to use a historical CEA year; default latest")
    factor_set_version: Optional[str] = None
    reusable_item_uses_default: int = Field(default=5, ge=1, le=1000,
                                            description="Expected number of uses for items marked reusable (user assumption)")


# ------------------------------------------------------------------ transport
class TransportMode(str, Enum):
    flight = "flight"
    train = "train"
    bus = "bus"
    car = "car"
    taxi = "taxi"
    motorcycle = "motorcycle"
    autorickshaw = "autorickshaw"
    electric_vehicle = "electric_vehicle"
    other = "other"


VEHICLE_MODES = {TransportMode.car, TransportMode.taxi, TransportMode.motorcycle, TransportMode.autorickshaw,
                 TransportMode.electric_vehicle}


class TransportEntry(BaseModel):
    id: str = Field(default_factory=_id)
    label: Optional[str] = None
    mode: TransportMode
    group: Optional[str] = Field(default=None, description="attendees / speakers / staff / logistics")
    origin: Optional[str] = None
    destination: Optional[str] = None
    distance_km: Optional[float] = Field(default=None, ge=0, description="ONE-WAY distance per journey")
    distance_unit: Literal["km", "miles"] = "km"
    distance_source: Literal["user", "estimated_airport", "estimated_geocode", "estimated_route"] = "user"
    passengers: int = Field(default=1, ge=0)
    trip_type: Literal["one_way", "return"] = "return"
    trips: int = Field(default=1, ge=1, description="Number of times this journey is made")
    vehicle_type: Optional[str] = Field(default=None, description="e.g. hatchback, sedan, suv, muv, small, medium, large, city, coach, national, suburban, metro, international")
    fuel_type: Optional[str] = Field(default=None, description="petrol, diesel, cng, lpg, hybrid, phev, bev, unknown")
    occupancy: Optional[float] = Field(default=None, gt=0, description="Persons per vehicle incl. driver if travelling (vehicle modes)")
    vehicles: Optional[int] = Field(default=None, ge=1, description="Number of vehicles, if known (overrides passengers/occupancy)")
    flight_class: Literal["average", "economy", "premium_economy", "business", "first"] = "economy"
    flight_scope: Optional[Literal["domestic", "international"]] = None
    touches_uk: bool = False
    region: Optional[str] = Field(default=None, description="ISO2 country of the journey; defaults to conference country")
    fuel_litres: Optional[float] = Field(default=None, ge=0, description="Actual fuel used (fuel-based method, overrides distance)")
    custom_factor: Optional[float] = Field(default=None, ge=0, description="User/supplier factor in kg CO2e per custom_factor_unit")
    custom_factor_unit: Optional[Literal["passenger.km", "vehicle.km"]] = None
    custom_factor_source: Optional[str] = None
    data_type: DataType = "actual"

    @model_validator(mode="after")
    def _check(self):
        if self.mode == TransportMode.other and self.custom_factor is None and self.fuel_litres is None:
            raise ValueError("Mode 'other' requires a custom emission factor or fuel quantity")
        if self.custom_factor is not None and self.custom_factor_unit is None:
            raise ValueError("custom_factor_unit is required when a custom factor is given")
        return self


# ------------------------------------------------------------------ accommodation
class AccommodationEntry(BaseModel):
    id: str = Field(default_factory=_id)
    label: Optional[str] = None
    hotel_name: Optional[str] = None
    country: str = "India"
    guests: Optional[int] = Field(default=None, ge=0, description="Participants staying overnight")
    rooms: Optional[int] = Field(default=None, ge=0)
    guests_per_room: Optional[float] = Field(default=None, gt=0)
    nights: int = Field(ge=0)
    accommodation_type: Optional[str] = Field(default="hotel", description="Informational; no class-specific factors are published")
    hotel_factor_kg_per_room_night: Optional[float] = Field(default=None, ge=0, description="Hotel-specific factor if supplied by the hotel")
    hotel_factor_source: Optional[str] = None
    # actual-energy method (for the share of the hotel used by the conference)
    electricity_kwh: Optional[float] = Field(default=None, ge=0)
    grid_country_code: Optional[str] = None
    diesel_litres: Optional[float] = Field(default=None, ge=0)
    lpg_kg: Optional[float] = Field(default=None, ge=0)
    natural_gas_m3: Optional[float] = Field(default=None, ge=0)
    data_type: DataType = "actual"

    @model_validator(mode="after")
    def _check(self):
        if not any([self.rooms, self.guests, self.electricity_kwh]):
            raise ValueError("Provide rooms, guests or actual energy data for each accommodation entry")
        return self


# ------------------------------------------------------------------ energy
class EquipmentLoad(BaseModel):
    name: str
    power_kw: float = Field(gt=0, description="Rated electrical power per unit (kW)")
    quantity: int = Field(default=1, ge=1)
    hours_per_day: float = Field(gt=0, le=24)
    days: Optional[int] = Field(default=None, ge=1)


class EnergyData(BaseModel):
    not_applicable: bool = False
    grid_electricity_kwh: Optional[float] = Field(default=None, ge=0, description="Metered grid electricity, total")
    renewable_certified_kwh: float = Field(default=0, ge=0, description="Part of grid kWh covered by RECs / green tariff (market-based only)")
    onsite_renewable_kwh: float = Field(default=0, ge=0, description="Self-generated on-site renewable consumed (not from grid)")
    grid_country_code: Optional[str] = None
    supplier_factor_kg_per_kwh: Optional[float] = Field(default=None, ge=0, description="Supplier-specific factor (market-based)")
    diesel_generator_litres: Optional[float] = Field(default=None, ge=0)
    petrol_generator_litres: Optional[float] = Field(default=None, ge=0)
    lpg_kg: Optional[float] = Field(default=None, ge=0)
    lpg_litres: Optional[float] = Field(default=None, ge=0)
    natural_gas_m3: Optional[float] = Field(default=None, ge=0)
    # estimation inputs (used ONLY when metered grid electricity is absent)
    ac_power_kw: Optional[float] = Field(default=None, gt=0, description="Total electrical input of AC plant (kW)")
    ac_hours_per_day: Optional[float] = Field(default=None, gt=0, le=24)
    lighting_power_kw: Optional[float] = Field(default=None, gt=0)
    lighting_hours_per_day: Optional[float] = Field(default=None, gt=0, le=24)
    equipment: list[EquipmentLoad] = Field(default_factory=list)
    data_type: DataType = "actual"

    @model_validator(mode="after")
    def _check(self):
        if self.grid_electricity_kwh is not None and self.renewable_certified_kwh > self.grid_electricity_kwh:
            raise ValueError("Certified renewable kWh cannot exceed total grid electricity")
        return self


# ------------------------------------------------------------------ food
MealService = Literal["breakfast", "lunch", "dinner", "snack"]
Diet = Literal["vegetarian", "vegan", "non_vegetarian_chicken", "non_vegetarian_fish", "non_vegetarian_mutton",
               "non_vegetarian_beef", "non_vegetarian_pork", "non_vegetarian_egg", "snack_refreshment", "snack_refreshment_coffee"]


class MealEntry(BaseModel):
    id: str = Field(default_factory=_id)
    service: MealService
    diet: Diet
    count: int = Field(ge=0)
    data_type: DataType = "actual"


class IngredientEntry(BaseModel):
    id: str = Field(default_factory=_id)
    service: Literal["breakfast", "lunch", "dinner", "snack", "beverages", "other"] = "other"
    food_key: str = Field(description="factor key, e.g. food.rice")
    quantity: float = Field(ge=0)
    unit: Literal["kg", "g", "tonne", "litre"] = "kg"
    data_type: DataType = "actual"


class BottledWater(BaseModel):
    bottles: int = Field(ge=0)
    volume_litres: float = Field(default=0.5, gt=0, le=25)
    bottle_mass_g: Optional[float] = Field(default=None, gt=0, le=1000, description="PET mass per empty bottle (check supplier spec)")
    recycled_pet: bool = False
    data_type: DataType = "actual"


class FoodData(BaseModel):
    not_applicable: bool = False
    meals: list[MealEntry] = Field(default_factory=list)
    ingredients: list[IngredientEntry] = Field(default_factory=list)
    bottled_water: Optional[BottledWater] = None

    @model_validator(mode="after")
    def _no_double_count(self):
        meal_services = {m.service for m in self.meals if m.count > 0}
        ing_services = {i.service for i in self.ingredients if i.service in ("breakfast", "lunch", "dinner", "snack")}
        clash = meal_services & ing_services
        if clash:
            raise ValueError(
                f"Meal-based and ingredient-based methods were both used for: {', '.join(sorted(clash))}. "
                "Use one method per meal service to avoid double counting.")
        return self


# ------------------------------------------------------------------ waste
WasteMaterial = Literal["food", "paper", "cardboard", "plastic", "glass", "metal", "mixed", "textiles"]


class WasteEntry(BaseModel):
    id: str = Field(default_factory=_id)
    material: WasteMaterial
    generated_kg: float = Field(ge=0)
    landfill_kg: float = Field(default=0, ge=0)
    recycling_kg: float = Field(default=0, ge=0)
    composting_kg: float = Field(default=0, ge=0)
    incineration_kg: float = Field(default=0, ge=0)
    anaerobic_digestion_kg: float = Field(default=0, ge=0)
    data_type: DataType = "actual"

    @model_validator(mode="after")
    def _routes(self):
        routed = self.landfill_kg + self.recycling_kg + self.composting_kg + self.incineration_kg + self.anaerobic_digestion_kg
        if routed > self.generated_kg + 1e-9:
            raise ValueError(f"{self.material}: waste assigned to disposal routes ({routed:g} kg) exceeds waste generated ({self.generated_kg:g} kg)")
        return self


class WasteData(BaseModel):
    not_applicable: bool = False
    entries: list[WasteEntry] = Field(default_factory=list)


# ------------------------------------------------------------------ materials
class MaterialEntry(BaseModel):
    id: str = Field(default_factory=_id)
    item: str = Field(description="e.g. Printed programmes, PVC banners, Lanyards")
    material_key: str = Field(description="factor key, e.g. materials.paper.virgin")
    quantity: float = Field(ge=0)
    unit: Literal["kg", "g", "tonne", "items", "pages"] = "kg"
    unit_mass_g: Optional[float] = Field(default=None, gt=0, description="Mass per item (required when unit = items)")
    paper_gsm: Optional[float] = Field(default=80, gt=0)
    sheet_size: Literal["A3", "A4", "A5"] = "A4"
    double_sided: bool = False
    reusable: bool = False
    expected_uses: Optional[int] = Field(default=None, ge=1)
    data_type: DataType = "actual"

    @model_validator(mode="after")
    def _check(self):
        if self.unit == "items" and self.unit_mass_g is None:
            raise ValueError(f"'{self.item}': mass per item (g) is required when quantity is given as items")
        if self.unit == "pages" and not self.material_key.startswith("materials.paper"):
            raise ValueError(f"'{self.item}': 'pages' can only be used with paper materials")
        return self


class MaterialsData(BaseModel):
    not_applicable: bool = False
    entries: list[MaterialEntry] = Field(default_factory=list)


class Offsets(BaseModel):
    tonnes_co2e: float = Field(default=0, ge=0)
    standard: Optional[str] = Field(default=None, description="e.g. Gold Standard, Verra VCS")
    retirement_reference: Optional[str] = None


# ------------------------------------------------------------------ root
class ConferenceInput(BaseModel):
    basic: BasicInfo
    settings: CalculationSettings = Field(default_factory=CalculationSettings)
    transport: list[TransportEntry] = Field(default_factory=list)
    transport_not_applicable: bool = False
    accommodation: list[AccommodationEntry] = Field(default_factory=list)
    accommodation_not_applicable: bool = False
    energy: Optional[EnergyData] = None
    food: Optional[FoodData] = None
    waste: Optional[WasteData] = None
    materials: Optional[MaterialsData] = None
    offsets: Offsets = Field(default_factory=Offsets)

    @field_validator("transport")
    @classmethod
    def _unique_ids(cls, v):
        ids = [e.id for e in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate transport entry ids")
        return v
