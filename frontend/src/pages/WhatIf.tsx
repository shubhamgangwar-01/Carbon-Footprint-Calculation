import { FlaskConical, Loader2, Play, RotateCcw, Wand2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { ComparisonBars, ScenarioBars } from "../charts/Charts";
import { Alert, Card, Field, NumberInput, Select, Spinner } from "../components/ui";
import { ResultsHeader, useCalculation } from "../dashboard/useCalculation";
import { api, formatApiError } from "../services/api";
import type { ConferenceInput, Scenario } from "../types";
import { fmt } from "../utils/format";

const PARAM_META: Record<string, { label: string; unit?: string; min?: number; max?: number; options?: { value: string; label: string }[] }> = {
  share_pct: { label: "Share switched", unit: "%", min: 0, max: 100 },
  reduction_pct: { label: "Reduction", unit: "%", min: 0, max: 100 },
  virtual_pct: { label: "Attendees online", unit: "%", min: 0, max: 100 },
  max_km: { label: "Max. flight distance", unit: "km", min: 100, max: 3000 },
  uses: { label: "Expected uses", unit: "events", min: 1, max: 50 },
  modes: { label: "Modes", options: [{ value: "flight", label: "Flights" }, { value: "flight,car,taxi", label: "Flights, cars & taxis" }, { value: "all", label: "All modes" }] },
  target: { label: "Replace with", options: [{ value: "vegetarian", label: "Vegetarian" }, { value: "vegan", label: "Vegan" }] },
  mode: { label: "Renewable type", options: [{ value: "certificates", label: "Certificates / green tariff" }, { value: "onsite", label: "On-site solar" }] },
};

function ResultBox({ s }: { s: Scenario }) {
  const up = s.reduction_kg < 0;
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-xl bg-slate-50 p-4"><div className="text-xs text-slate-500">Baseline</div><div className="text-xl font-bold">{fmt(s.baseline_kg / 1000, 2)} t</div></div>
        <div className="rounded-xl bg-slate-50 p-4"><div className="text-xs text-slate-500">Scenario</div><div className="text-xl font-bold">{fmt(s.scenario_kg / 1000, 2)} t</div></div>
        <div className={`rounded-xl p-4 ${up ? "bg-red-50" : "bg-forest-50"}`}><div className="text-xs text-slate-500">{up ? "Increase" : "Reduction"}</div>
          <div className={`text-xl font-bold ${up ? "text-red-700" : "text-forest-800"}`}>{fmt(Math.abs(s.reduction_kg) / 1000, 2)} t ({Math.abs(s.reduction_pct).toFixed(1)}%)</div></div>
      </div>
      {Math.abs(s.market_reduction_kg - s.reduction_kg) > 0.5 && (
        <Alert kind="info">Market-based: {fmt(s.baseline_market_kg / 1000, 2)} → {fmt(s.scenario_market_kg / 1000, 2)} t CO₂e (−{s.market_reduction_pct.toFixed(1)}%). Location-based (headline) totals are unaffected by certificates.</Alert>
      )}
      <p className="text-sm text-slate-600">{s.description}</p>
      <ComparisonBars s={s} />
    </div>
  );
}

export default function WhatIf() {
  const { calcId } = useParams();
  const id = Number(calcId);
  const { calc, error } = useCalculation(id);
  const [presets, setPresets] = useState<{ preset: string; title: string; category: string; params: Record<string, unknown> }[]>([]);
  const [params, setParams] = useState<Record<string, Record<string, unknown>>>({});
  const [running, setRunning] = useState<string | null>(null);
  const [active, setActive] = useState<Scenario | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [custom, setCustom] = useState<ConferenceInput | null>(null);
  const [basis, setBasis] = useState<"location" | "market">("location");
  useEffect(() => { api.presets().then((p) => { setPresets(p); setParams(Object.fromEntries(p.map((x) => [x.preset, x.params]))); }); }, []);
  useEffect(() => { if (calc) api.getConference(calc.conference_id).then((c) => setCustom(c.input)).catch(() => null); }, [calc]);
  if (error) return <div className="mx-auto max-w-3xl p-6"><Alert kind="error">{error}</Alert></div>;
  if (!calc) return <Spinner />;

  const run = async (preset: string) => {
    setRunning(preset); setErr(null);
    try { setActive(await api.runScenario(id, { preset, params: params[preset] })); } catch (e) { setErr(formatApiError(e)); } finally { setRunning(null); }
  };
  const runCustom = async () => {
    if (!custom) return;
    setRunning("custom"); setErr(null);
    try { setActive(await api.runScenario(id, { scenario_input: custom, title: "Custom scenario", description: "Arrangement edited on the what-if page." })); }
    catch (e) { setErr(formatApiError(e)); } finally { setRunning(null); }
  };
  const resetCustom = () => api.getConference(calc.conference_id).then((c) => setCustom(c.input));

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <ResultsHeader calc={calc} />
      <div className="grid gap-6 lg:grid-cols-5">
        <div className="space-y-6 lg:col-span-2">
          <Card title="Scenario presets" subtitle="Each runs the same engine and factor set on a modified copy of your inputs." icon={<FlaskConical size={20} />}>
            <div className="space-y-3">
              {presets.map((p) => {
                const pre = calc.scenarios.find((s) => s.preset === p.preset);
                return (
                  <div key={p.preset} className={`rounded-xl border p-3 ${active?.preset === p.preset ? "border-forest-400 bg-mint-50" : "border-slate-200"}`}>
                    <div className="flex items-start justify-between gap-2">
                      <div><div className="text-sm font-medium text-slate-900">{p.title}</div>
                        {pre && <div className="text-xs text-slate-500">{pre.applicable ? `Default: ${pre.reduction_kg >= 0 ? "−" : "+"}${fmt(Math.abs(pre.reduction_kg) / 1000, 2)} t (${Math.abs(pre.reduction_pct).toFixed(1)}%)${pre.market_reduction_kg !== pre.reduction_kg ? ` · market −${pre.market_reduction_pct.toFixed(1)}%` : ""}` : "Not applicable to your data"}</div>}
                      </div>
                      <button className="btn-secondary shrink-0 px-3 py-1.5" onClick={() => run(p.preset)} disabled={!!running}>{running === p.preset ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}Run</button>
                    </div>
                    {Object.keys(p.params).length > 0 && (
                      <div className="mt-2 grid grid-cols-2 gap-2">
                        {Object.entries(params[p.preset] || {}).map(([k, v]) => {
                          const m = PARAM_META[k] || { label: k };
                          return (
                            <Field key={k} label={m.label} unit={m.unit}>
                              {m.options ? <Select value={String(v)} onChange={(nv) => setParams((s) => ({ ...s, [p.preset]: { ...s[p.preset], [k]: nv } }))} options={m.options} /> :
                                <NumberInput value={Number(v)} min={m.min} onChange={(nv) => setParams((s) => ({ ...s, [p.preset]: { ...s[p.preset], [k]: Math.min(m.max ?? Infinity, nv ?? 0) } }))} />}
                            </Field>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </Card>
        </div>
        <div className="space-y-6 lg:col-span-3">
          {err && <Alert kind="error">{err}</Alert>}
          <Card title={active ? active.title : "Scenario result"} subtitle={active ? "Compared with the stored baseline calculation" : "Run a preset or build a custom scenario"}>
            {active ? <ResultBox s={active} /> : <p className="text-sm text-slate-500">Choose a scenario on the left. Results compare category by category against your baseline.</p>}
          </Card>
          <Card title="All scenarios at default settings" subtitle="Estimated change in total emissions"
            actions={<div className="w-44"><Select ariaLabel="Basis" value={basis} onChange={(v) => setBasis(v as "location" | "market")} options={[{ value: "location", label: "Location-based" }, { value: "market", label: "Market-based" }]} /></div>}>
            <ScenarioBars scenarios={calc.scenarios} basis={basis} />
          </Card>
          {custom && (
            <Card title="Custom scenario builder" subtitle="Change transport modes, passengers, meals and electricity, then compare." icon={<Wand2 size={20} />}
              actions={<div className="flex gap-2"><button className="btn-ghost" onClick={resetCustom}><RotateCcw size={14} />Reset</button>
                <button className="btn-primary" onClick={runCustom} disabled={!!running}>{running === "custom" ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}Compare</button></div>}>
              <div className="space-y-4">
                {custom.transport.length > 0 && (
                  <div className="overflow-x-auto"><table className="w-full min-w-[560px] text-sm">
                    <thead><tr><th className="th">Journey</th><th className="th">Mode</th><th className="th">Passengers</th><th className="th">Occupancy</th></tr></thead>
                    <tbody>{custom.transport.map((t, i) => (
                      <tr key={t.id} className="border-t border-slate-100">
                        <td className="td text-xs">{t.label || `${t.origin || ""} → ${t.destination || ""}`}</td>
                        <td className="td"><Select value={t.mode} onChange={(v) => setCustom((c) => c && ({ ...c, transport: c.transport.map((x, j) => j === i ? { ...x, mode: v, vehicle_type: v === "bus" ? "coach" : v === "train" ? "national" : x.vehicle_type, occupancy: ["car", "taxi", "motorcycle", "autorickshaw", "electric_vehicle"].includes(v) ? (x.occupancy || 1) : null, vehicles: null } : x) }))}
                          options={["flight", "train", "bus", "car", "taxi", "electric_vehicle", "motorcycle", "autorickshaw"].map((m) => ({ value: m, label: m.replace("_", " ") }))} /></td>
                        <td className="td w-28"><NumberInput value={t.passengers} step="1" onChange={(v) => setCustom((c) => c && ({ ...c, transport: c.transport.map((x, j) => j === i ? { ...x, passengers: v ?? 0 } : x) }))} /></td>
                        <td className="td w-28">{["car", "taxi", "motorcycle", "autorickshaw", "electric_vehicle"].includes(t.mode) ? <NumberInput value={t.occupancy} min={0.1} onChange={(v) => setCustom((c) => c && ({ ...c, transport: c.transport.map((x, j) => j === i ? { ...x, occupancy: v, vehicles: null } : x) }))} /> : "–"}</td>
                      </tr>))}</tbody></table></div>
                )}
                {custom.food?.meals && custom.food.meals.length > 0 && (
                  <div className="grid gap-2 sm:grid-cols-3">
                    {custom.food.meals.map((m, i) => (
                      <Field key={m.id} label={`${m.service} · ${m.diet.replace(/_/g, " ")}`}>
                        <NumberInput step="1" value={m.count} onChange={(v) => setCustom((c) => c && c.food ? ({ ...c, food: { ...c.food, meals: c.food.meals.map((x, j) => j === i ? { ...x, count: v ?? 0 } : x) } }) : c)} />
                      </Field>
                    ))}
                  </div>
                )}
                {custom.energy && custom.energy.grid_electricity_kwh != null && (
                  <div className="grid gap-2 sm:grid-cols-3">
                    <Field label="Grid electricity" unit="kWh"><NumberInput value={custom.energy.grid_electricity_kwh} onChange={(v) => setCustom((c) => c && c.energy ? ({ ...c, energy: { ...c.energy, grid_electricity_kwh: v, renewable_certified_kwh: Math.min(c.energy.renewable_certified_kwh, v ?? 0) } }) : c)} /></Field>
                    <Field label="Renewable certified" unit="kWh"><NumberInput value={custom.energy.renewable_certified_kwh} onChange={(v) => setCustom((c) => c && c.energy ? ({ ...c, energy: { ...c.energy, renewable_certified_kwh: v ?? 0 } }) : c)} /></Field>
                    <Field label="Diesel generator" unit="litres"><NumberInput value={custom.energy.diesel_generator_litres} onChange={(v) => setCustom((c) => c && c.energy ? ({ ...c, energy: { ...c.energy, diesel_generator_litres: v } }) : c)} /></Field>
                  </div>
                )}
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
