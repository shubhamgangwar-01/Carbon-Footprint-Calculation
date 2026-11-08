import { CheckCircle2, CircleDashed, Loader2, MinusCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Alert, Card } from "../components/ui";
import { api, formatApiError } from "../services/api";
import { useConference } from "../state/ConferenceContext";
import { fmtKg } from "../utils/format";
import type { CalcResult } from "../types";

export default function ReviewStep() {
  const { input } = useConference();
  const [preview, setPreview] = useState<CalcResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(true);
  useEffect(() => {
    setBusy(true);
    api.preview(input)
      .then((r) => { setPreview(r); setErr(null); })
      .catch(async () => {
        const v = await api.validate(input).catch(() => null);
        setErr(v && !v.valid ? v.errors.map((e) => `${e.loc.join(" › ")}: ${e.msg.replace(/^Value error, /, "")}`).join("\n") : formatApiError("Could not calculate a preview"));
      })
      .finally(() => setBusy(false));
  }, [input]);
  const modules = [
    { k: "transport", l: "Transport", n: input.transport.length, na: input.transport_not_applicable, unit: "journeys" },
    { k: "accommodation", l: "Accommodation", n: input.accommodation.length, na: input.accommodation_not_applicable, unit: "entries" },
    { k: "energy", l: "Venue & energy", n: input.energy && (input.energy.grid_electricity_kwh != null || input.energy.diesel_generator_litres || input.energy.equipment.length || input.energy.ac_power_kw) ? 1 : 0, na: !!input.energy?.not_applicable, unit: "" },
    { k: "food", l: "Food & beverages", n: (input.food?.meals.length || 0) + (input.food?.ingredients.length || 0) + (input.food?.bottled_water ? 1 : 0), na: !!input.food?.not_applicable, unit: "items" },
    { k: "waste", l: "Waste", n: input.waste?.entries.length || 0, na: !!input.waste?.not_applicable, unit: "streams" },
    { k: "materials", l: "Materials", n: input.materials?.entries.length || 0, na: !!input.materials?.not_applicable, unit: "items" },
  ];
  return (
    <div className="space-y-6">
      <Card title="Review & calculate" subtitle="Check completeness before calculating. You can return to any step.">
        <ul className="divide-y divide-slate-100">
          {modules.map((m) => (
            <li key={m.k} className="flex items-center justify-between py-3 text-sm">
              <span className="flex items-center gap-2">
                {m.na ? <MinusCircle size={18} className="text-slate-400" /> : m.n ? <CheckCircle2 size={18} className="text-forest-600" /> : <CircleDashed size={18} className="text-amber-500" />}
                <Link to={`/calculator/${m.k}`} className="font-medium hover:text-forest-700">{m.l}</Link>
              </span>
              <span className="text-slate-500">{m.na ? "Declared not applicable" : m.n ? `${m.n} ${m.unit}` : "Not reported - will not be counted"}</span>
            </li>
          ))}
        </ul>
      </Card>
      <Card title="Live preview" subtitle="Unsaved estimate from the calculation engine; click Calculate to store results, scenarios and recommendations.">
        {busy ? <div className="flex items-center gap-2 text-sm text-slate-500"><Loader2 size={16} className="animate-spin" />Calculating…</div> :
          err ? <Alert kind="error">{err}</Alert> : preview && (
            <div className="space-y-3">
              <div className="flex flex-wrap gap-6">
                <div><div className="text-xs uppercase text-slate-500">Total</div><div className="text-2xl font-bold text-forest-800">{fmtKg(preview.total_kg)} CO₂e</div></div>
                <div><div className="text-xs uppercase text-slate-500">Per participant</div><div className="text-2xl font-bold text-slate-800">{fmtKg(preview.per_participant_kg)}</div></div>
              </div>
              {preview.issues.filter((i) => i.level !== "info").map((i, k) => <Alert key={k} kind={i.level === "error" ? "error" : "warning"}>{i.message}</Alert>)}
            </div>
          )}
      </Card>
    </div>
  );
}
