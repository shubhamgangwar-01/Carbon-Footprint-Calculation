import { Building2, Users } from "lucide-react";
import { Card, Field, NumberInput, Select, Toggle } from "../components/ui";
import { useConference } from "../state/ConferenceContext";
import type { BasicInfo, ConferenceInput } from "../types";

export const COUNTRIES: { code: string; name: string }[] = [
  { code: "IN", name: "India" }, { code: "GB", name: "United Kingdom" }, { code: "US", name: "United States" },
  { code: "AE", name: "United Arab Emirates" }, { code: "SG", name: "Singapore" }, { code: "DE", name: "Germany" },
  { code: "FR", name: "France" }, { code: "AU", name: "Australia" }, { code: "JP", name: "Japan" }, { code: "TH", name: "Thailand" },
  { code: "MY", name: "Malaysia" }, { code: "ID", name: "Indonesia" }, { code: "CN", name: "China" }, { code: "ZA", name: "South Africa" },
  { code: "BR", name: "Brazil" }, { code: "CA", name: "Canada" }, { code: "IT", name: "Italy" }, { code: "ES", name: "Spain" },
  { code: "NL", name: "Netherlands" }, { code: "LK", name: "Sri Lanka" }, { code: "NP", name: "Nepal" }, { code: "BD", name: "Bangladesh" },
];

export function validateBasic(i: ConferenceInput): string | null {
  const b = i.basic;
  if (!b.name.trim()) return "Please enter the conference name (Step 1).";
  if (!b.days && !(b.start_date && b.end_date)) return "Please enter start and end dates or the number of conference days (Step 1).";
  if (b.start_date && b.end_date && b.end_date < b.start_date) return "The end date must be on or after the start date.";
  if (b.attendees < 0) return "Attendees cannot be negative.";
  if (b.attendees + b.speakers + b.organisers_staff + b.volunteers === 0) return "Please enter the number of participants (Step 1).";
  return null;
}

export default function BasicInfoForm() {
  const { input, setInput } = useConference();
  const b = input.basic;
  const set = <K extends keyof BasicInfo>(k: K, v: BasicInfo[K]) => setInput((p) => ({ ...p, basic: { ...p.basic, [k]: v } }));
  const span = b.start_date && b.end_date ? Math.round((+new Date(b.end_date) - +new Date(b.start_date)) / 86400000) + 1 : null;
  const total = b.attendees + b.speakers + b.organisers_staff + b.volunteers;
  return (
    <div className="space-y-6">
      <Card title="Conference information" subtitle="Basic details define the reporting boundary and the per-participant and per-day metrics." icon={<Building2 size={20} />}>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Conference name" className="sm:col-span-2" error={!b.name.trim() ? "Required" : undefined}>
            <input className="input" value={b.name} onChange={(e) => set("name", e.target.value)} placeholder="e.g. National Conference on Climate Action 2027" />
          </Field>
          <Field label="Country" tip="Determines default grid electricity, road/rail and hotel factors. India-specific factors are used for India.">
            <Select value={b.country_code} onChange={(v) => setInput((p) => ({ ...p, basic: { ...p.basic, country_code: v, country: COUNTRIES.find((c) => c.code === v)?.name || v } }))}
              options={COUNTRIES.map((c) => ({ value: c.code, label: c.name }))} />
          </Field>
          <Field label="State / city" optional><input className="input" value={b.state_city ?? ""} onChange={(e) => set("state_city", e.target.value)} placeholder="e.g. Bengaluru, Karnataka" /></Field>
          <Field label="Venue name" optional><input className="input" value={b.venue_name ?? ""} onChange={(e) => set("venue_name", e.target.value)} /></Field>
          <Field label="Venue area" unit="m²" optional tip="Used for reporting context only. Electricity is never estimated from floor area alone (no robust published intensity).">
            <NumberInput value={b.venue_area_m2} onChange={(v) => set("venue_area_m2", v)} />
          </Field>
          <Field label="Start date"><input type="date" className="input" value={b.start_date ?? ""} onChange={(e) => set("start_date", e.target.value || null)} /></Field>
          <Field label="End date" error={b.start_date && b.end_date && b.end_date < b.start_date ? "End date is before start date" : undefined}>
            <input type="date" className="input" value={b.end_date ?? ""} onChange={(e) => set("end_date", e.target.value || null)} />
          </Field>
          <Field label="Number of conference days" unit="days" tip="Calculated from the dates if left empty. Can be fewer than the date span (e.g. non-consecutive days).">
            <NumberInput value={b.days} min={1} step="1" onChange={(v) => set("days", v)} placeholder={span ? `${span} (from dates)` : ""} />
          </Field>
          <Field label="Conference type">
            <Select value={b.conference_type} onChange={(v) => set("conference_type", v)} options={[
              { value: "academic", label: "Academic" }, { value: "corporate", label: "Corporate" }, { value: "government", label: "Government" },
              { value: "exhibition", label: "Exhibition" }, { value: "other", label: "Other" }]} />
          </Field>
          <Field label="Format">
            <Select value={b.format} onChange={(v) => set("format", v)} options={[
              { value: "offline", label: "In person (offline)" }, { value: "hybrid", label: "Hybrid" }, { value: "online", label: "Online" }]} />
          </Field>
        </div>
      </Card>
      <Card title="Participants" subtitle="Enter each group separately - totals are used for the per-participant footprint." icon={<Users size={20} />}>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="In-person attendees" tip="Delegates attending in person, EXCLUDING speakers, organisers/staff and volunteers.">
            <NumberInput value={b.attendees} step="1" onChange={(v) => set("attendees", v ?? 0)} />
          </Field>
          <Field label="Speakers"><NumberInput value={b.speakers} step="1" onChange={(v) => set("speakers", v ?? 0)} /></Field>
          <Field label="Organisers & staff"><NumberInput value={b.organisers_staff} step="1" onChange={(v) => set("organisers_staff", v ?? 0)} /></Field>
          <Field label="Volunteers"><NumberInput value={b.volunteers} step="1" onChange={(v) => set("volunteers", v ?? 0)} /></Field>
          {b.format !== "offline" && (
            <Field label="Virtual attendees" tip="Excluded from per-participant metrics. Device/network emissions of online participation are not quantified (no robust open factor).">
              <NumberInput value={b.virtual_attendees} step="1" onChange={(v) => set("virtual_attendees", v ?? 0)} />
            </Field>
          )}
          <div className="flex items-end"><div className="w-full rounded-xl bg-mint-50 px-4 py-2.5 text-sm"><span className="text-slate-500">Total in person: </span><b className="text-forest-800">{total.toLocaleString()}</b></div></div>
        </div>
      </Card>
      <Card title="Calculation settings" subtitle="Transparent methodological choices.">
        <div className="space-y-3">
          <Toggle checked={input.settings.include_radiative_forcing} onChange={(v) => setInput((p) => ({ ...p, settings: { ...p.settings, include_radiative_forcing: v } }))}
            label="Include non-CO₂ effects of aviation (radiative forcing)"
            tip="DESNZ applies a 1.7× multiplier to flight CO₂ for contrails, NOx and water vapour. Recommended - excluding it understates aviation's climate impact by ~40%." />
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Offsets / carbon credits retired" unit="t CO₂e" optional tip="Shown separately. Offsets never reduce gross emissions in this tool (GHG Protocol).">
              <NumberInput value={input.offsets.tonnes_co2e} onChange={(v) => setInput((p) => ({ ...p, offsets: { ...p.offsets, tonnes_co2e: v ?? 0 } }))} />
            </Field>
            <Field label="Offset standard" optional>
              <input className="input" value={input.offsets.standard ?? ""} placeholder="e.g. Gold Standard" onChange={(e) => setInput((p) => ({ ...p, offsets: { ...p.offsets, standard: e.target.value } }))} />
            </Field>
          </div>
        </div>
      </Card>
    </div>
  );
}
