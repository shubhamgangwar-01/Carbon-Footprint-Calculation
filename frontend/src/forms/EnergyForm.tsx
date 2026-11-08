import { Plus, Trash2, Zap } from "lucide-react";
import { Alert, Card, DataTypeSelect, Field, NotApplicable, NumberInput, Select } from "../components/ui";
import { useConference } from "../state/ConferenceContext";
import type { EnergyData } from "../types";

const empty = (): EnergyData => ({ not_applicable: false, grid_electricity_kwh: null, renewable_certified_kwh: 0, onsite_renewable_kwh: 0, equipment: [], data_type: "actual" });

export default function EnergyForm() {
  const { input, setInput, options } = useConference();
  const en = input.energy || empty();
  const set = (patch: Partial<EnergyData>) => setInput((p) => ({ ...p, energy: { ...(p.energy || empty()), ...patch } }));
  const metered = en.grid_electricity_kwh !== null && en.grid_electricity_kwh !== undefined;
  const grid = options?.grid_factors.find((g) => g.country_code === input.basic.country_code);
  const days = input.basic.days || 1;
  const estKwh = (en.ac_power_kw && en.ac_hours_per_day ? en.ac_power_kw * en.ac_hours_per_day * days : 0)
    + (en.lighting_power_kw && en.lighting_hours_per_day ? en.lighting_power_kw * en.lighting_hours_per_day * days : 0)
    + en.equipment.reduce((s, q) => s + q.power_kw * q.quantity * q.hours_per_day * (q.days || days), 0);
  return (
    <div className="space-y-6">
      <Card title="Venue & energy" icon={<Zap size={20} />} subtitle="Metered electricity and fuel records are strongly preferred. Load-based estimates are used only if no meter reading is entered.">
        <NotApplicable checked={en.not_applicable} onChange={(v) => set({ not_applicable: v })} what="Venue energy (e.g. fully online event)" />
        {!en.not_applicable && (
          <div className="mt-4 space-y-4">
            {grid ? <Alert kind="info">Grid factor for {input.basic.country}: <b>{grid.factor.toFixed(3)} kg CO₂e/kWh</b> ({grid.source}).</Alert> :
              <Alert kind="warning">No published grid factor is stored for {input.basic.country}. Enter a supplier-specific factor below, otherwise electricity cannot be calculated.</Alert>}
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <Field label="Grid electricity (metered)" unit="kWh" tip="Total electricity drawn from the grid for the event (venue sub-meter or bill), including set-up days.">
                <NumberInput value={en.grid_electricity_kwh} onChange={(v) => set({ grid_electricity_kwh: v })} />
              </Field>
              <Field label="…of which renewable certified" unit="kWh" tip="Covered by renewable energy certificates (I-RECs/RECs) or a green tariff. Reduces the market-based total only; location-based total is unchanged (GHG Protocol Scope 2)."
                error={metered && en.renewable_certified_kwh > (en.grid_electricity_kwh || 0) ? "Cannot exceed total grid electricity" : undefined}>
                <NumberInput value={en.renewable_certified_kwh} onChange={(v) => set({ renewable_certified_kwh: v ?? 0 })} />
              </Field>
              <Field label="On-site renewable (self-generated)" unit="kWh" tip="E.g. rooftop solar consumed directly - zero operational emissions.">
                <NumberInput value={en.onsite_renewable_kwh} onChange={(v) => set({ onsite_renewable_kwh: v ?? 0 })} />
              </Field>
              <Field label="Diesel generator" unit="litres" tip="Fuel logs for DG sets (common at Indian venues)."><NumberInput value={en.diesel_generator_litres} onChange={(v) => set({ diesel_generator_litres: v })} /></Field>
              <Field label="Petrol generator" unit="litres" optional><NumberInput value={en.petrol_generator_litres} onChange={(v) => set({ petrol_generator_litres: v })} /></Field>
              <Field label="LPG (cooking / heating)" unit="kg" optional><NumberInput value={en.lpg_kg} onChange={(v) => set({ lpg_kg: v })} /></Field>
              <Field label="Natural gas / PNG" unit="m³" optional><NumberInput value={en.natural_gas_m3} onChange={(v) => set({ natural_gas_m3: v })} /></Field>
              {!grid && <Field label="Supplier factor" unit="kg CO₂e/kWh" tip="From your electricity supplier."><NumberInput value={en.supplier_factor_kg_per_kwh} onChange={(v) => set({ supplier_factor_kg_per_kwh: v })} /></Field>}
              {input.basic.country_code === "IN" && options?.grid_years && (
                <Field label="Grid factor year" tip="Use the latest year unless reproducing a past event.">
                  <Select value={input.settings.grid_reporting_year ?? ""} onChange={(v) => setInput((p) => ({ ...p, settings: { ...p.settings, grid_reporting_year: v || null } }))}
                    options={[{ value: "", label: "Latest (FY 2025-26)" }, ...options.grid_years.slice().reverse().map((y) => ({ value: y, label: `FY ${y}` }))]} />
                </Field>
              )}
              <Field label="Data type"><DataTypeSelect value={en.data_type} onChange={(v) => set({ data_type: v as EnergyData["data_type"] })} /></Field>
            </div>
          </div>
        )}
      </Card>
      {!en.not_applicable && (
        <Card title="Estimate electricity from equipment loads" subtitle={metered ? "Not used - metered electricity has been entered (prevents double counting)." : "Only if no meter reading is available. Enter rated electrical power - not cooling capacity."}>
          {metered && <div className="mb-3"><Alert kind="success">Metered electricity takes priority; the estimates below are ignored in the calculation.</Alert></div>}
          <fieldset disabled={metered} className={metered ? "opacity-50" : ""}>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Field label="AC electrical input" unit="kW" tip="Total electrical power of the air-conditioning plant serving the event space."><NumberInput value={en.ac_power_kw} onChange={(v) => set({ ac_power_kw: v })} /></Field>
              <Field label="AC operating hours" unit="h/day"><NumberInput value={en.ac_hours_per_day} onChange={(v) => set({ ac_hours_per_day: v })} /></Field>
              <Field label="Lighting load" unit="kW"><NumberInput value={en.lighting_power_kw} onChange={(v) => set({ lighting_power_kw: v })} /></Field>
              <Field label="Lighting hours" unit="h/day"><NumberInput value={en.lighting_hours_per_day} onChange={(v) => set({ lighting_hours_per_day: v })} /></Field>
            </div>
            <div className="mt-4 space-y-2">
              {en.equipment.map((q, i) => (
                <div key={i} className="grid grid-cols-2 gap-2 sm:grid-cols-6">
                  <input className="input col-span-2" placeholder="Equipment" value={q.name} onChange={(e) => set({ equipment: en.equipment.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)) })} />
                  <NumberInput ariaLabel="kW per unit" placeholder="kW/unit" value={q.power_kw} onChange={(v) => set({ equipment: en.equipment.map((x, j) => (j === i ? { ...x, power_kw: v ?? 0 } : x)) })} />
                  <NumberInput ariaLabel="Quantity" placeholder="qty" value={q.quantity} onChange={(v) => set({ equipment: en.equipment.map((x, j) => (j === i ? { ...x, quantity: v ?? 1 } : x)) })} />
                  <NumberInput ariaLabel="Hours per day" placeholder="h/day" value={q.hours_per_day} onChange={(v) => set({ equipment: en.equipment.map((x, j) => (j === i ? { ...x, hours_per_day: v ?? 0 } : x)) })} />
                  <button className="btn-ghost text-red-600" aria-label="Remove" onClick={() => set({ equipment: en.equipment.filter((_, j) => j !== i) })}><Trash2 size={16} /></button>
                </div>
              ))}
              <button className="btn-secondary" onClick={() => set({ equipment: [...en.equipment, { name: "", power_kw: 1, quantity: 1, hours_per_day: 8 }] })}><Plus size={14} />Add equipment</button>
            </div>
            {!metered && estKwh > 0 && <p className="mt-3 text-sm text-slate-600">Estimated electricity: <b>{estKwh.toLocaleString(undefined, { maximumFractionDigits: 0 })} kWh</b> over {days} day(s) (flagged as estimated).</p>}
          </fieldset>
        </Card>
      )}
    </div>
  );
}
