import { Plus, Recycle, Trash2 } from "lucide-react";
import { Alert, Card, DataTypeSelect, Field, NotApplicable, NumberInput, Select } from "../components/ui";
import { useConference } from "../state/ConferenceContext";
import type { WasteEntry } from "../types";
import { uid } from "../utils/format";

const MATERIALS = [
  { v: "food", l: "Food waste" }, { v: "paper", l: "Paper" }, { v: "cardboard", l: "Cardboard" }, { v: "plastic", l: "Plastic" },
  { v: "glass", l: "Glass" }, { v: "metal", l: "Metal (cans)" }, { v: "mixed", l: "Mixed / general waste" }, { v: "textiles", l: "Textiles" },
];
const ROUTES: { k: keyof WasteEntry; r: string; l: string }[] = [
  { k: "landfill_kg", r: "landfill", l: "Landfill" }, { k: "recycling_kg", r: "recycling", l: "Recycling" },
  { k: "composting_kg", r: "composting", l: "Composting" }, { k: "incineration_kg", r: "incineration", l: "Incineration" },
  { k: "anaerobic_digestion_kg", r: "anaerobic_digestion", l: "Anaerobic digestion" },
];

export default function WasteForm() {
  const { input, setInput, options } = useConference();
  const wd = input.waste || { not_applicable: false, entries: [] };
  const setEntries = (entries: WasteEntry[]) => setInput((p) => ({ ...p, waste: { ...(p.waste || { not_applicable: false, entries: [] }), entries } }));
  const upd = (id: string, patch: Partial<WasteEntry>) => setEntries(wd.entries.map((w) => (w.id === id ? { ...w, ...patch } : w)));
  return (
    <div className="space-y-6">
      <Card title="Waste management" icon={<Recycle size={20} />} subtitle="Weigh waste by stream and record where it goes. Waste not assigned to a route is conservatively treated as landfill and flagged.">
        <NotApplicable checked={wd.not_applicable} onChange={(v) => setInput((p) => ({ ...p, waste: { ...(p.waste || { entries: [] }), not_applicable: v } }))} what="Waste" />
        {!wd.not_applicable && <div className="mt-3"><Alert kind="info">Factors follow the DESNZ / GHG Protocol cut-off method: recycling and composting carry only collection & transport; no recycling credits are claimed. UK landfill gas-capture assumptions likely <b>under-estimate</b> Indian landfill emissions.</Alert></div>}
      </Card>
      {!wd.not_applicable && wd.entries.map((w) => {
        const routed = ROUTES.reduce((s, r) => s + (Number(w[r.k]) || 0), 0);
        const over = routed > w.generated_kg + 1e-9;
        const allowed = options?.waste_routes[w.material] || ROUTES.map((r) => r.r);
        return (
          <div key={w.id} className="card p-5">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Field label="Material"><Select value={w.material} onChange={(v) => upd(w.id, { material: v })} options={MATERIALS.map((m) => ({ value: m.v, label: m.l }))} /></Field>
              <Field label="Total generated" unit="kg"><NumberInput value={w.generated_kg} onChange={(v) => upd(w.id, { generated_kg: v ?? 0 })} /></Field>
              <Field label="Data type"><DataTypeSelect value={w.data_type} onChange={(v) => upd(w.id, { data_type: v as WasteEntry["data_type"] })} /></Field>
              <div className="flex items-end justify-end"><button className="btn-ghost text-red-600" onClick={() => setEntries(wd.entries.filter((x) => x.id !== w.id))}><Trash2 size={16} />Remove</button></div>
              {ROUTES.filter((r) => allowed.includes(r.r)).map((r) => (
                <Field key={r.k} label={r.l} unit="kg"><NumberInput value={w[r.k] as number} error={over} onChange={(v) => upd(w.id, { [r.k]: v ?? 0 } as Partial<WasteEntry>)} /></Field>
              ))}
            </div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100" aria-hidden>
              <div className={`h-full ${over ? "bg-red-500" : "bg-forest-500"}`} style={{ width: `${Math.min(100, w.generated_kg ? (100 * routed) / w.generated_kg : 0)}%` }} />
            </div>
            <p className={`mt-1 text-xs ${over ? "text-red-600" : "text-slate-500"}`}>
              {over ? `Assigned ${routed} kg exceeds the ${w.generated_kg} kg generated - please correct.` :
                `${routed} of ${w.generated_kg} kg assigned${w.generated_kg - routed > 0 ? ` · ${(w.generated_kg - routed).toFixed(1)} kg unassigned → landfill (default)` : ""}`}
            </p>
          </div>
        );
      })}
      {!wd.not_applicable && (
        <button className="btn-secondary" onClick={() => setEntries([...wd.entries, { id: uid(), material: MATERIALS.find((m) => !wd.entries.some((e) => e.material === m.v))?.v || "mixed", generated_kg: 0, landfill_kg: 0, recycling_kg: 0, composting_kg: 0, incineration_kg: 0, anaerobic_digestion_kg: 0, data_type: "actual" }])}>
          <Plus size={14} />Add waste stream
        </button>
      )}
    </div>
  );
}
