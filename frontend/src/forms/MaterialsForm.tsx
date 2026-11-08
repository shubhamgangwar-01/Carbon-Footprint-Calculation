import { Package, Plus, Trash2 } from "lucide-react";
import { Alert, Card, DataTypeSelect, Field, NotApplicable, NumberInput, Select, Toggle } from "../components/ui";
import { useConference } from "../state/ConferenceContext";
import type { MaterialEntry } from "../types";
import { uid } from "../utils/format";

const PRESETS: { item: string; key: string; unit: string; hint: string }[] = [
  { item: "Printed programmes / brochures", key: "materials.paper.virgin", unit: "pages", hint: "Enter printed pages; paper mass is computed from sheet size and grammage." },
  { item: "PVC banners & standees", key: "materials.plastic.pvc", unit: "kg", hint: "Weigh or use supplier mass." },
  { item: "Fabric banners", key: "materials.textile.clothing", unit: "kg", hint: "" },
  { item: "Plastic ID cards / badges", key: "materials.plastic.pvc", unit: "items", hint: "" },
  { item: "Lanyards (polyester)", key: "materials.plastic.pet", unit: "items", hint: "" },
  { item: "Conference bags / kits (cotton)", key: "materials.textile.clothing", unit: "items", hint: "" },
  { item: "Non-woven bags (PP)", key: "materials.plastic.pp", unit: "items", hint: "" },
  { item: "Packaging", key: "materials.board.virgin", unit: "kg", hint: "" },
  { item: "Other material", key: "materials.plastic.average", unit: "kg", hint: "" },
];

export default function MaterialsForm() {
  const { input, setInput, options } = useConference();
  const md = input.materials || { not_applicable: false, entries: [] };
  const setEntries = (entries: MaterialEntry[]) => setInput((p) => ({ ...p, materials: { ...(p.materials || { not_applicable: false, entries: [] }), entries } }));
  const upd = (id: string, patch: Partial<MaterialEntry>) => setEntries(md.entries.map((m) => (m.id === id ? { ...m, ...patch } : m)));
  const mats = options?.materials || [];
  return (
    <div className="space-y-6">
      <Card title="Materials & procurement" icon={<Package size={20} />} subtitle="Cradle-to-gate production emissions of purchased event materials (DESNZ material-use factors, UK proxy). Items without a reliable mass can be left out.">
        <NotApplicable checked={md.not_applicable} onChange={(v) => setInput((p) => ({ ...p, materials: { ...(p.materials || { entries: [] }), not_applicable: v } }))} what="Purchased materials" />
      </Card>
      {!md.not_applicable && md.entries.map((m) => (
        <div key={m.id} className="card p-5">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Item"><input className="input" value={m.item} onChange={(e) => upd(m.id, { item: e.target.value })} /></Field>
            <Field label="Material" tip="Material factor used. Polyester uses the PET polymer factor (weaving/dyeing excluded); cotton uses the DESNZ textiles factor.">
              <Select value={m.material_key} onChange={(v) => upd(m.id, { material_key: v, unit: !v.startsWith("materials.paper") && m.unit === "pages" ? "kg" : m.unit })}
                options={mats.map((x) => ({ value: x.key, label: `${x.label} (${x.factor.toFixed(2)} kg/kg)` }))} />
            </Field>
            <Field label="Quantity"><NumberInput value={m.quantity} onChange={(v) => upd(m.id, { quantity: v ?? 0 })} /></Field>
            <Field label="Unit">
              <Select value={m.unit} onChange={(v) => upd(m.id, { unit: v })} options={[{ value: "kg", label: "kg" }, { value: "g", label: "g" }, { value: "tonne", label: "tonne" }, { value: "items", label: "items" },
                ...(m.material_key.startsWith("materials.paper") ? [{ value: "pages", label: "printed pages" }] : [])]} />
            </Field>
            {m.unit === "items" && <Field label="Mass per item" unit="g" tip="Weigh one item or use the supplier specification. Required." error={!m.unit_mass_g ? "Required" : undefined}><NumberInput value={m.unit_mass_g} onChange={(v) => upd(m.id, { unit_mass_g: v })} /></Field>}
            {m.unit === "pages" && <>
              <Field label="Paper grammage" unit="g/m²"><NumberInput value={m.paper_gsm} onChange={(v) => upd(m.id, { paper_gsm: v })} /></Field>
              <Field label="Sheet size"><Select value={m.sheet_size} onChange={(v) => upd(m.id, { sheet_size: v })} options={[{ value: "A4", label: "A4" }, { value: "A3", label: "A3" }, { value: "A5", label: "A5" }]} /></Field>
              <div className="flex items-end pb-2"><Toggle checked={m.double_sided} onChange={(v) => upd(m.id, { double_sided: v })} label="Double-sided" /></div>
            </>}
            <div className="flex items-end gap-3 pb-2"><Toggle checked={m.reusable} onChange={(v) => upd(m.id, { reusable: v })} label="Reusable" tip="Production emissions are spread over the expected number of uses (your assumption)." /></div>
            {m.reusable && <Field label="Expected uses" unit="events"><NumberInput value={m.expected_uses ?? input.settings.reusable_item_uses_default} min={1} step="1" onChange={(v) => upd(m.id, { expected_uses: v })} /></Field>}
            <Field label="Data type"><DataTypeSelect value={m.data_type} onChange={(v) => upd(m.id, { data_type: v as MaterialEntry["data_type"] })} /></Field>
            <div className="flex items-end justify-end"><button className="btn-ghost text-red-600" onClick={() => setEntries(md.entries.filter((x) => x.id !== m.id))}><Trash2 size={16} />Remove</button></div>
          </div>
        </div>
      ))}
      {!md.not_applicable && (
        <Card title="Add an item">
          <div className="flex flex-wrap gap-2">
            {PRESETS.map((p) => (
              <button key={p.item} className="btn-secondary" onClick={() => setEntries([...md.entries, { id: uid(), item: p.item, material_key: p.key, quantity: 0, unit: p.unit, unit_mass_g: null, paper_gsm: 80, sheet_size: "A4", double_sided: false, reusable: false, expected_uses: null, data_type: "actual" }])}>
                <Plus size={14} />{p.item}
              </button>
            ))}
          </div>
          <div className="mt-3"><Alert kind="info">Printing energy/ink, sewing and dyeing are excluded (no reliable generic factors); only material production is counted.</Alert></div>
        </Card>
      )}
    </div>
  );
}
