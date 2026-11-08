from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel

CATEGORIES = ["transportation", "accommodation", "energy", "food", "waste", "materials"]
CATEGORY_LABELS = {
    "transportation": "Transportation", "accommodation": "Accommodation", "energy": "Venue & energy",
    "food": "Food & beverages", "waste": "Waste", "materials": "Materials & procurement",
}


class CalculationLine(BaseModel):
    line_id: str
    category: str
    activity: str
    description: str
    entry_ref: Optional[str] = None
    quantity: float
    quantity_unit: str
    factor_id: Optional[str] = None
    factor_value: Optional[float] = None
    factor_unit: Optional[str] = None
    factor_source: Optional[str] = None
    factor_geography: Optional[str] = None
    emissions_kg: float
    data_type: Literal["actual", "estimated", "default"]
    data_quality: Literal["high", "medium", "low"]
    data_quality_score: Optional[float] = None
    formula: str
    notes: list[str] = []
    is_proxy: bool = False
    scope_note: Optional[str] = None


class Issue(BaseModel):
    level: Literal["error", "warning", "info"]
    category: str
    message: str
    entry_ref: Optional[str] = None


class CategoryResult(BaseModel):
    category: str
    label: str
    status: Literal["calculated", "not_reported", "not_applicable", "incomplete"]
    emissions_kg: float
    share_pct: float
    line_count: int


class CalculationResult(BaseModel):
    engine_version: str
    factor_set_version: str
    calculated_at: str
    conference_name: str
    total_kg: float
    total_tonnes: float
    per_participant_kg: Optional[float]
    per_day_kg: Optional[float]
    per_participant_day_kg: Optional[float]
    participants: int
    days: int
    location_based_electricity_kg: float
    market_based_electricity_kg: float
    total_market_based_kg: float
    offsets_tonnes: float
    net_tonnes_after_offsets: float
    by_category: list[CategoryResult]
    top_activities: list[dict[str, Any]]
    data_type_breakdown: dict[str, dict[str, float]]
    data_quality: dict[str, Any]
    completeness: dict[str, Any]
    lines: list[CalculationLine]
    issues: list[Issue]
    assumptions: list[str]
    exclusions: list[str]
    factors_used: list[dict[str, Any]]
