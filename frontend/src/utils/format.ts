export const CATEGORY_META: Record<string, { label: string; color: string; short: string }> = {
  transportation: { label: "Transportation", color: "#2a78d6", short: "Transport" },
  accommodation: { label: "Accommodation", color: "#eb6834", short: "Accommodation" },
  energy: { label: "Venue & energy", color: "#1baf7a", short: "Energy" },
  food: { label: "Food & beverages", color: "#eda100", short: "Food" },
  waste: { label: "Waste", color: "#e87ba4", short: "Waste" },
  materials: { label: "Materials & procurement", color: "#008300", short: "Materials" },
};

export const fmt = (v: number | null | undefined, d = 1) =>
  v === null || v === undefined || Number.isNaN(v) ? "–" : v.toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d });

export const fmtKg = (kg: number | null | undefined) => {
  if (kg === null || kg === undefined) return "–";
  return Math.abs(kg) >= 1000 ? `${fmt(kg / 1000, 2)} t` : `${fmt(kg, 1)} kg`;
};

export const uid = () => Math.random().toString(16).slice(2, 12);

export const num = (v: string): number | null => (v === "" || v === null ? null : Number(v));

export const STATUS_STYLE: Record<string, string> = {
  calculated: "bg-forest-100 text-forest-800",
  not_reported: "bg-slate-100 text-slate-600",
  not_applicable: "bg-slate-100 text-slate-500",
  incomplete: "bg-amber-100 text-amber-800",
};
export const DQ_STYLE: Record<string, string> = {
  high: "bg-forest-100 text-forest-800", medium: "bg-amber-50 text-amber-800", low: "bg-red-50 text-red-700",
};
export const DT_STYLE: Record<string, string> = {
  actual: "bg-forest-100 text-forest-800", estimated: "bg-sky-50 text-sky-800", default: "bg-slate-100 text-slate-700",
};
