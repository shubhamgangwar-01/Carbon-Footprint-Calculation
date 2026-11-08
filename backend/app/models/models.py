"""Relational schema.

`conferences.input_json` holds the full validated ConferenceInput (the source of
truth for re-calculation); the per-module entry tables hold the same data in
normalised form for querying, reporting and auditing. They are rewritten
together in one transaction on every save.

`calculation_results` stores the input snapshot, the full result (every line
with its factor_id and value) and the factor-set version, so a stored result and
any report generated from it never change when factors are later updated.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


def now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="user")  # guest | user | admin
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    conferences: Mapped[list["Conference"]] = relationship(back_populates="owner")


class Conference(Base):
    __tablename__ = "conferences"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    conference_type: Mapped[str | None] = mapped_column(String(30))
    format: Mapped[str | None] = mapped_column(String(20))
    country: Mapped[str | None] = mapped_column(String(100))
    country_code: Mapped[str | None] = mapped_column(String(2))
    state_city: Mapped[str | None] = mapped_column(String(200))
    venue_name: Mapped[str | None] = mapped_column(String(200))
    venue_area_m2: Mapped[float | None] = mapped_column(Float)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    days: Mapped[int | None] = mapped_column(Integer)
    input_json: Mapped[dict] = mapped_column(JSON)
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    owner: Mapped[User] = relationship(back_populates="conferences")
    participants: Mapped[list["ConferenceParticipant"]] = relationship(cascade="all, delete-orphan")
    transport: Mapped[list["TransportationEntry"]] = relationship(cascade="all, delete-orphan")
    accommodation: Mapped[list["AccommodationEntry"]] = relationship(cascade="all, delete-orphan")
    energy: Mapped[list["EnergyEntry"]] = relationship(cascade="all, delete-orphan")
    food: Mapped[list["FoodEntry"]] = relationship(cascade="all, delete-orphan")
    waste: Mapped[list["WasteEntry"]] = relationship(cascade="all, delete-orphan")
    materials: Mapped[list["MaterialEntry"]] = relationship(cascade="all, delete-orphan")
    calculations: Mapped[list["CalculationResultRow"]] = relationship(cascade="all, delete-orphan", back_populates="conference")


class ConferenceParticipant(Base):
    __tablename__ = "conference_participants"
    id: Mapped[int] = mapped_column(primary_key=True)
    conference_id: Mapped[int] = mapped_column(ForeignKey("conferences.id", ondelete="CASCADE"), index=True)
    group: Mapped[str] = mapped_column(String(30))  # attendees | speakers | organisers_staff | volunteers | virtual_attendees
    count: Mapped[int] = mapped_column(Integer)


class _Entry:
    id: Mapped[int] = mapped_column(primary_key=True)
    entry_uid: Mapped[str] = mapped_column(String(40))
    data_type: Mapped[str] = mapped_column(String(12), default="actual")
    data: Mapped[dict] = mapped_column(JSON)


class TransportationEntry(_Entry, Base):
    __tablename__ = "transportation_entries"
    conference_id: Mapped[int] = mapped_column(ForeignKey("conferences.id", ondelete="CASCADE"), index=True)
    mode: Mapped[str] = mapped_column(String(30))
    group: Mapped[str | None] = mapped_column(String(40))
    origin: Mapped[str | None] = mapped_column(String(200))
    destination: Mapped[str | None] = mapped_column(String(200))
    distance_km: Mapped[float | None] = mapped_column(Float)
    distance_source: Mapped[str | None] = mapped_column(String(30))
    passengers: Mapped[int] = mapped_column(Integer)
    trip_type: Mapped[str] = mapped_column(String(10))
    trips: Mapped[int] = mapped_column(Integer)
    vehicle_type: Mapped[str | None] = mapped_column(String(40))
    fuel_type: Mapped[str | None] = mapped_column(String(20))
    occupancy: Mapped[float | None] = mapped_column(Float)
    flight_class: Mapped[str | None] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(20), default="form")  # form | csv | excel


class AccommodationEntry(_Entry, Base):
    __tablename__ = "accommodation_entries"
    conference_id: Mapped[int] = mapped_column(ForeignKey("conferences.id", ondelete="CASCADE"), index=True)
    country: Mapped[str | None] = mapped_column(String(100))
    rooms: Mapped[int | None] = mapped_column(Integer)
    guests: Mapped[int | None] = mapped_column(Integer)
    nights: Mapped[int] = mapped_column(Integer)


class EnergyEntry(_Entry, Base):
    __tablename__ = "energy_entries"
    conference_id: Mapped[int] = mapped_column(ForeignKey("conferences.id", ondelete="CASCADE"), index=True)
    grid_electricity_kwh: Mapped[float | None] = mapped_column(Float)
    renewable_certified_kwh: Mapped[float | None] = mapped_column(Float)
    diesel_generator_litres: Mapped[float | None] = mapped_column(Float)


class FoodEntry(_Entry, Base):
    __tablename__ = "food_entries"
    conference_id: Mapped[int] = mapped_column(ForeignKey("conferences.id", ondelete="CASCADE"), index=True)
    entry_type: Mapped[str] = mapped_column(String(20))  # meal | ingredient | bottled_water
    service: Mapped[str | None] = mapped_column(String(20))
    item: Mapped[str] = mapped_column(String(80))
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(20))


class WasteEntry(_Entry, Base):
    __tablename__ = "waste_entries"
    conference_id: Mapped[int] = mapped_column(ForeignKey("conferences.id", ondelete="CASCADE"), index=True)
    material: Mapped[str] = mapped_column(String(20))
    generated_kg: Mapped[float] = mapped_column(Float)


class MaterialEntry(_Entry, Base):
    __tablename__ = "material_entries"
    conference_id: Mapped[int] = mapped_column(ForeignKey("conferences.id", ondelete="CASCADE"), index=True)
    item: Mapped[str] = mapped_column(String(200))
    material_key: Mapped[str] = mapped_column(String(80))
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(10))


class EmissionFactorSource(Base):
    __tablename__ = "emission_factor_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(Text)
    publisher: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    landing_page: Mapped[str | None] = mapped_column(Text)
    licence: Mapped[str | None] = mapped_column(Text)
    version: Mapped[str | None] = mapped_column(String(120))
    reporting_year: Mapped[str | None] = mapped_column(String(80))
    geography: Mapped[str | None] = mapped_column(Text)
    local_path: Mapped[str | None] = mapped_column(Text)
    sha256: Mapped[str | None] = mapped_column(String(64))
    downloaded_at: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str | None] = mapped_column(String(20))
    notes: Mapped[str | None] = mapped_column(Text)


class EmissionFactor(Base):
    __tablename__ = "emission_factors"
    __table_args__ = (UniqueConstraint("factor_id", name="uq_factor_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    factor_id: Mapped[str] = mapped_column(String(160), index=True)
    factor_key: Mapped[str] = mapped_column(String(120), index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    activity: Mapped[str] = mapped_column(String(120))
    subcategory: Mapped[str] = mapped_column(Text)
    emission_factor: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(60))
    activity_unit: Mapped[str] = mapped_column(String(40))
    gas_basis: Mapped[str] = mapped_column(String(10))
    geography: Mapped[str] = mapped_column(Text)
    reporting_year: Mapped[str] = mapped_column(String(80))
    source_id: Mapped[str] = mapped_column(String(80), index=True)
    source_name: Mapped[str] = mapped_column(Text)
    source_publisher: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    source_reference: Mapped[str | None] = mapped_column(Text)
    dataset_version: Mapped[str] = mapped_column(String(80), index=True)
    system_boundary: Mapped[str | None] = mapped_column(Text)
    greenhouse_gases_included: Mapped[str | None] = mapped_column(Text)
    methodology: Mapped[str | None] = mapped_column(Text)
    derivation: Mapped[dict | None] = mapped_column(JSON)
    data_quality: Mapped[dict | None] = mapped_column(JSON)
    uncertainty: Mapped[str | None] = mapped_column(Text)
    licence: Mapped[str | None] = mapped_column(Text)
    last_updated: Mapped[str | None] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    extra: Mapped[dict | None] = mapped_column(JSON)
    created_by: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    def to_record(self) -> dict:
        r = {c: getattr(self, c) for c in (
            "factor_id", "factor_key", "category", "activity", "subcategory", "emission_factor", "unit", "activity_unit",
            "gas_basis", "geography", "reporting_year", "source_id", "source_name", "source_publisher", "source_url",
            "source_reference", "dataset_version", "system_boundary", "greenhouse_gases_included", "methodology",
            "derivation", "data_quality", "uncertainty", "licence", "last_updated", "is_active")}
        r["created_by"] = self.created_by
        if self.extra:
            r.update(self.extra)
        return r


class CalculationResultRow(Base):
    __tablename__ = "calculation_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    conference_id: Mapped[int] = mapped_column(ForeignKey("conferences.id", ondelete="CASCADE"), index=True)
    input_snapshot: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
    recommendations: Mapped[list | None] = mapped_column(JSON)
    total_kg: Mapped[float] = mapped_column(Float)
    factor_set_version: Mapped[str] = mapped_column(String(40))
    engine_version: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    conference: Mapped[Conference] = relationship(back_populates="calculations")
    scenarios: Mapped[list["ScenarioComparison"]] = relationship(cascade="all, delete-orphan")
    reports: Mapped[list["GeneratedReport"]] = relationship(cascade="all, delete-orphan")


class ScenarioComparison(Base):
    __tablename__ = "scenario_comparisons"
    id: Mapped[int] = mapped_column(primary_key=True)
    calculation_id: Mapped[int] = mapped_column(ForeignKey("calculation_results.id", ondelete="CASCADE"), index=True)
    preset: Mapped[str] = mapped_column(String(40))
    params: Mapped[dict | None] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
    reduction_kg: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class GeneratedReport(Base):
    __tablename__ = "generated_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    calculation_id: Mapped[int] = mapped_column(ForeignKey("calculation_results.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer)
    pdf: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
