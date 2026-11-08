// Mirrors backend/app/schemas/conference.py and results.py
export type DataType = "actual" | "estimated" | "default";

export interface BasicInfo {
  name: string; country: string; country_code: string; state_city?: string | null; location?: string | null;
  venue_name?: string | null; venue_area_m2?: number | null; start_date?: string | null; end_date?: string | null;
  days?: number | null; attendees: number; speakers: number; organisers_staff: number; volunteers: number;
  virtual_attendees: number; conference_type: string; format: string;
}
export interface Settings { include_radiative_forcing: boolean; grid_reporting_year?: string | null; reusable_item_uses_default: number }
export interface TransportEntry {
  id: string; label?: string | null; mode: string; group?: string | null; origin?: string | null; destination?: string | null;
  distance_km?: number | null; distance_unit?: "km" | "miles"; distance_source?: string; passengers: number;
  trip_type: "one_way" | "return"; trips: number; vehicle_type?: string | null; fuel_type?: string | null;
  occupancy?: number | null; vehicles?: number | null; flight_class: string; touches_uk?: boolean; region?: string | null;
  fuel_litres?: number | null; custom_factor?: number | null; custom_factor_unit?: string | null; custom_factor_source?: string | null;
  data_type: DataType;
}
export interface AccommodationEntry {
  id: string; label?: string | null; hotel_name?: string | null; country: string; guests?: number | null; rooms?: number | null;
  guests_per_room?: number | null; nights: number; accommodation_type?: string | null;
  hotel_factor_kg_per_room_night?: number | null; hotel_factor_source?: string | null; electricity_kwh?: number | null;
  diesel_litres?: number | null; lpg_kg?: number | null; natural_gas_m3?: number | null; data_type: DataType;
}
export interface EquipmentLoad { name: string; power_kw: number; quantity: number; hours_per_day: number; days?: number | null }
export interface EnergyData {
  not_applicable: boolean; grid_electricity_kwh?: number | null; renewable_certified_kwh: number; onsite_renewable_kwh: number;
  grid_country_code?: string | null; supplier_factor_kg_per_kwh?: number | null; diesel_generator_litres?: number | null;
  petrol_generator_litres?: number | null; lpg_kg?: number | null; lpg_litres?: number | null; natural_gas_m3?: number | null;
  ac_power_kw?: number | null; ac_hours_per_day?: number | null; lighting_power_kw?: number | null; lighting_hours_per_day?: number | null;
  equipment: EquipmentLoad[]; data_type: DataType;
}
export interface MealEntry { id: string; service: string; diet: string; count: number; data_type: DataType }
export interface IngredientEntry { id: string; service: string; food_key: string; quantity: number; unit: string; data_type: DataType }
export interface BottledWater { bottles: number; volume_litres: number; bottle_mass_g?: number | null; recycled_pet: boolean; data_type: DataType }
export interface FoodData { not_applicable: boolean; meals: MealEntry[]; ingredients: IngredientEntry[]; bottled_water?: BottledWater | null }
export interface WasteEntry {
  id: string; material: string; generated_kg: number; landfill_kg: number; recycling_kg: number; composting_kg: number;
  incineration_kg: number; anaerobic_digestion_kg: number; data_type: DataType;
}
export interface MaterialEntry {
  id: string; item: string; material_key: string; quantity: number; unit: string; unit_mass_g?: number | null;
  paper_gsm?: number | null; sheet_size: string; double_sided: boolean; reusable: boolean; expected_uses?: number | null; data_type: DataType;
}
export interface ConferenceInput {
  basic: BasicInfo; settings: Settings; transport: TransportEntry[]; transport_not_applicable: boolean;
  accommodation: AccommodationEntry[]; accommodation_not_applicable: boolean; energy?: EnergyData | null;
  food?: FoodData | null; waste?: { not_applicable: boolean; entries: WasteEntry[] } | null;
  materials?: { not_applicable: boolean; entries: MaterialEntry[] } | null;
  offsets: { tonnes_co2e: number; standard?: string | null; retirement_reference?: string | null };
}

export interface CalcLine {
  line_id: string; category: string; activity: string; description: string; entry_ref?: string; quantity: number; quantity_unit: string;
  factor_id?: string; factor_value?: number; factor_unit?: string; factor_source?: string; factor_geography?: string;
  emissions_kg: number; data_type: DataType; data_quality: "high" | "medium" | "low"; data_quality_score?: number;
  formula: string; notes: string[]; is_proxy: boolean;
}
export interface Issue { level: "error" | "warning" | "info"; category: string; message: string; entry_ref?: string }
export interface CategoryResult { category: string; label: string; status: string; emissions_kg: number; share_pct: number; line_count: number }
export interface CalcResult {
  engine_version: string; factor_set_version: string; calculated_at: string; conference_name: string;
  total_kg: number; total_tonnes: number; per_participant_kg: number | null; per_day_kg: number | null; per_participant_day_kg: number | null;
  participants: number; days: number; location_based_electricity_kg: number; market_based_electricity_kg: number;
  total_market_based_kg: number; offsets_tonnes: number; net_tonnes_after_offsets: number; by_category: CategoryResult[];
  top_activities: { category: string; activity: string; emissions_kg: number; share_pct: number }[];
  data_type_breakdown: Record<DataType, { emissions_kg: number; share_pct: number; lines: number }>;
  data_quality: { weighted_score: number | null; label: string | null; scale: string; proxy_factor_share_pct: number; uncertainty_rating: string;
    emissions_by_factor_quality_kg: Record<string, number> };
  completeness: { categories_calculated: number; categories_not_reported: string[]; categories_incomplete: string[];
    categories_not_applicable: string[]; entries_not_counted: number; is_complete: boolean };
  lines: CalcLine[]; issues: Issue[]; assumptions: string[]; exclusions: string[];
  factors_used: { factor_key: string; factor_id: string; value: number; unit: string; source: string; source_url: string;
    dataset_version: string; reporting_year: string; geography: string; system_boundary: string; data_quality: string }[];
}
export interface Scenario {
  preset: string; title: string; description: string; params: Record<string, unknown>; baseline_kg: number; scenario_kg: number;
  reduction_kg: number; reduction_pct: number; baseline_market_kg: number; scenario_market_kg: number; market_reduction_kg: number;
  market_reduction_pct: number; baseline_by_category: Record<string, number>; scenario_by_category: Record<string, number>;
  applicable: boolean; error?: string;
}
export interface Recommendation {
  rank: number; category: string; category_label: string; title: string; actions: string[]; evidence: string;
  potential_reduction_kg: number | null; potential_reduction_pct: number | null; potential_basis?: string | null;
  scenario: string | null; scenario_title?: string | null; related_scenarios: { preset: string; title: string; reduction_kg: number; reduction_pct: number }[];
}
export interface Calculation {
  id: number; conference_id: number; created_at: string; result: CalcResult; recommendations: Recommendation[];
  scenarios: Scenario[]; reports: { id: number; filename: string; created_at: string; sha256: string }[];
}
export interface Options {
  food_items: { key: string; label: string; factor: number; unit: string }[];
  meal_models: { key: string; label: string; factor: number }[];
  materials: { key: string; label: string; factor: number; unit: string }[];
  hotel_countries: { country: string; factor: number; key: string }[];
  waste_routes: Record<string, string[]>;
  grid_factors: { country_code: string; factor: number; source: string }[];
  grid_years: string[]; factor_set_version: string;
}
