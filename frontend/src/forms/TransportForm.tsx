import { Bike, Bus, Car, CarTaxiFront, Download, Loader2, MapPin, Plane, Plus, TrainFront, Trash2, Upload, Zap } from "lucide-react";
import { useRef, useState } from "react";
import { Alert, Card, DataTypeSelect, Field, NotApplicable, NumberInput, Select, Toggle } from "../components/ui";
import { api, formatApiError } from "../services/api";
import { useConference } from "../state/ConferenceContext";
import type { TransportEntry } from "../types";
import { uid } from "../utils/format";

const MODES = [
  { v: "flight", l: "Flight", i: Plane }, { v: "train", l: "Train / metro", i: TrainFront }, { v: "bus", l: "Bus / coach", i: Bus },
  { v: "car", l: "Car", i: Car }, { v: "taxi", l: "Taxi / cab", i: CarTaxiFront }, { v: "motorcycle", l: "Motorcycle / scooter", i: Bike },
  { v: "autorickshaw", l: "Auto-rickshaw", i: CarTaxiFront }, { v: "electric_vehicle", l: "Electric car", i: Zap }, { v: "other", l: "Other", i: MapPin },
];
const VEHICLE_OPTS: Record<string, { value: string; label: string }[]> = {
  car: [{ value: "hatchback", label: "Hatchback / small" }, { value: "sedan", label: "Sedan / medium" }, { value: "suv", label: "SUV / large" }, { value: "muv", label: "MUV / MPV" }],
  taxi: [{ value: "hatchback", label: "Hatchback" }, { value: "sedan", label: "Sedan" }, { value: "suv", label: "SUV / MUV" }],
  electric_vehicle: [{ value: "hatchback", label: "Small" }, { value: "sedan", label: "Medium" }, { value: "suv", label: "Large" }],
  motorcycle: [{ value: "scooter", label: "Scooter (<110 cc)" }, { value: "small", label: "Motorcycle <125 cc" }, { value: "medium", label: "Motorcycle <200 cc" }, { value: "large", label: "Motorcycle <500 cc" }],
  train: [{ value: "national", label: "Long-distance / intercity" }, { value: "suburban", label: "Suburban / local" }, { value: "metro", label: "Metro / light rail" }, { value: "international", label: "International rail" }],
  bus: [{ value: "city", label: "City / local bus" }, { value: "coach", label: "Coach / intercity / chartered shuttle" }],
};
const FUEL_OPTS: Record<string, { value: string; label: string }[]> = {
  car: [{ value: "petrol", label: "Petrol" }, { value: "diesel", label: "Diesel" }, { value: "cng", label: "CNG" }, { value: "hybrid", label: "Hybrid" }, { value: "phev", label: "Plug-in hybrid" }, { value: "lpg", label: "LPG" }],
  taxi: [{ value: "cng", label: "CNG" }, { value: "petrol", label: "Petrol" }, { value: "diesel", label: "Diesel" }, { value: "hybrid", label: "Hybrid" }, { value: "bev", label: "Electric" }],
  autorickshaw: [{ value: "cng", label: "CNG" }, { value: "petrol", label: "Petrol" }, { value: "diesel", label: "Diesel" }],
};
const VEHICLE_MODES = ["car", "taxi", "motorcycle", "autorickshaw", "electric_vehicle"];

const newEntry = (mode: string): TransportEntry => ({
  id: uid(), mode, passengers: 1, trip_type: "return", trips: 1, flight_class: "economy", data_type: "actual",
  distance_source: "user", distance_unit: "km", group: "attendees",
  vehicle_type: VEHICLE_OPTS[mode]?.[mode === "bus" ? 0 : 0]?.value ?? null, fuel_type: FUEL_OPTS[mode]?.[0]?.value ?? null,
  occupancy: VEHICLE_MODES.includes(mode) ? 1 : null,
});

function AirportInput({ value, onChange, label }: { value?: string | null; onChange: (v: string) => void; label: string }) {
  const [sugg, setSugg] = useState<{ iata: string; name: string; city: string; country: string }[]>([]);
  const t = useRef<number>();
  return (
    <div className="relative">
      <input className="input uppercase" aria-label={label} value={value ?? ""} placeholder="IATA e.g. DEL or city"
        onChange={(e) => {
          onChange(e.target.value);
          const q = e.target.value.trim();
          window.clearTimeout(t.current);
          if (q.length >= 2) t.current = window.setTimeout(() => api.airports(q).then(setSugg).catch(() => setSugg([])), 250);
          else setSugg([]);
        }} onBlur={() => setTimeout(() => setSugg([]), 200)} />
      {sugg.length > 0 && (
        <ul className="absolute z-30 mt-1 max-h-60 w-72 overflow-auto rounded-lg border border-slate-200 bg-white text-sm shadow-lg">
          {sugg.map((a) => (
            <li key={a.iata}><button type="button" className="w-full px-3 py-2 text-left hover:bg-mint-50" onMouseDown={() => { onChange(a.iata); setSugg([]); }}>
              <b>{a.iata}</b> · {a.city || a.name} <span className="text-xs text-slate-500">({a.country}) {a.name}</span>
            </button></li>
          ))}
        </ul>
      )}
    </div>
  );
}

function EntryCard({ e, update, remove }: { e: TransportEntry; update: (p: Partial<TransportEntry>) => void; remove: () => void }) {
  const [est, setEst] = useState<{ busy: boolean; msg?: string; err?: string }>({ busy: false });
  const isVehicle = VEHICLE_MODES.includes(e.mode);
  const Icon = MODES.find((m) => m.v === e.mode)?.i || MapPin;
  const estimate = async () => {
    if (!e.origin || !e.destination) { setEst({ busy: false, err: "Enter origin and destination first." }); return; }
    setEst({ busy: true });
    try {
      const r = await api.distance(e.origin, e.destination, e.mode === "flight" ? "flight" : "road");
      if (r.error || !r.distance_km) setEst({ busy: false, err: r.error || "No distance found" });
      else { update({ distance_km: r.distance_km, distance_source: r.source }); setEst({ busy: false, msg: `${r.distance_km} km - ${r.method}${r.note ? ". " + r.note : ""}` }); }
    } catch (x) { setEst({ busy: false, err: formatApiError(x) }); }
  };
  const legs = e.trip_type === "return" ? 2 : 1;
  const pkm = (e.distance_km || 0) * legs * e.trips * e.passengers;
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-card">
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <span className="rounded-lg bg-mint-100 p-2 text-forest-700"><Icon size={18} /></span>
        <Select ariaLabel="Mode" value={e.mode} onChange={(m) => update({ ...newEntry(m), id: e.id, label: e.label, passengers: e.passengers, origin: e.origin, destination: e.destination, distance_km: e.distance_km, trip_type: e.trip_type, trips: e.trips, group: e.group })}
          options={MODES.map((m) => ({ value: m.v, label: m.l }))} />
        <input className="input max-w-xs flex-1" aria-label="Label" placeholder="Label (optional) e.g. Speakers from Delhi" value={e.label ?? ""} onChange={(x) => update({ label: x.target.value })} />
        <button className="btn-ghost ml-auto text-red-600" onClick={remove} aria-label="Remove journey"><Trash2 size={16} /></button>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Origin">{e.mode === "flight" ? <AirportInput label="Origin" value={e.origin} onChange={(v) => update({ origin: v })} /> :
          <input className="input" value={e.origin ?? ""} onChange={(x) => update({ origin: x.target.value })} placeholder="City / place" />}</Field>
        <Field label="Destination">{e.mode === "flight" ? <AirportInput label="Destination" value={e.destination} onChange={(v) => update({ destination: v })} /> :
          <input className="input" value={e.destination ?? ""} onChange={(x) => update({ destination: x.target.value })} placeholder="City / venue" />}</Field>
        <Field label="One-way distance" unit={e.distance_unit || "km"} tip={e.mode === "flight" ? "Leave empty with IATA codes to use the great-circle distance automatically. DESNZ factors already include an 8% routing uplift." : "Distance for ONE direction of the journey. Return trips are doubled automatically."}
          error={!e.distance_km && !(e.mode === "flight" && e.origin && e.destination) && !e.fuel_litres ? "Distance required" : undefined}>
          <div className="flex gap-1">
            <NumberInput value={e.distance_km} onChange={(v) => update({ distance_km: v, distance_source: "user" })} />
            <button type="button" className="btn-secondary px-2" onClick={estimate} title="Estimate distance" aria-label="Estimate distance">{est.busy ? <Loader2 size={16} className="animate-spin" /> : <MapPin size={16} />}</button>
          </div>
        </Field>
        <Field label="Journey"><Select value={e.trip_type} onChange={(v) => update({ trip_type: v as TransportEntry["trip_type"] })} options={[{ value: "return", label: "Return (both ways)" }, { value: "one_way", label: "One way" }]} /></Field>
        <Field label="Passengers" tip="Number of participants making this journey."><NumberInput value={e.passengers} step="1" onChange={(v) => update({ passengers: v ?? 0 })} /></Field>
        <Field label="Number of trips" tip="How many times the journey is made, e.g. 3 for a daily hotel-venue commute over 3 days."><NumberInput value={e.trips} step="1" min={1} onChange={(v) => update({ trips: v ?? 1 })} /></Field>
        {e.mode === "flight" && (
          <Field label="Cabin class" tip="Premium cabins take more floor space per passenger, so emissions per passenger are higher.">
            <Select value={e.flight_class} onChange={(v) => update({ flight_class: v })} options={[{ value: "economy", label: "Economy" }, { value: "premium_economy", label: "Premium economy" }, { value: "business", label: "Business" }, { value: "first", label: "First" }, { value: "average", label: "Unknown / average" }]} />
          </Field>
        )}
        {VEHICLE_OPTS[e.mode] && (
          <Field label={e.mode === "train" ? "Rail type" : e.mode === "bus" ? "Bus type" : "Vehicle size"}>
            <Select value={e.vehicle_type} onChange={(v) => update({ vehicle_type: v })} options={VEHICLE_OPTS[e.mode]} />
          </Field>
        )}
        {FUEL_OPTS[e.mode] && <Field label="Fuel"><Select value={e.fuel_type} onChange={(v) => update({ fuel_type: v })} options={FUEL_OPTS[e.mode]} /></Field>}
        {isVehicle && (
          <Field label="Occupancy" unit="persons/vehicle" tip="Participants sharing each vehicle. Emissions are calculated per vehicle-km and shared, so passengers are not double counted. Leave as 1 if unknown (conservative).">
            <NumberInput value={e.occupancy} min={0.1} onChange={(v) => update({ occupancy: v })} />
          </Field>
        )}
        {isVehicle && <Field label="Number of vehicles" optional tip="If known, overrides passengers ÷ occupancy."><NumberInput value={e.vehicles} step="1" min={1} onChange={(v) => update({ vehicles: v })} /></Field>}
        <Field label="Participant group"><Select value={e.group} onChange={(v) => update({ group: v })} options={[{ value: "attendees", label: "Attendees" }, { value: "speakers", label: "Speakers" }, { value: "staff", label: "Organisers / staff" }, { value: "logistics", label: "Logistics / other" }]} /></Field>
        <Field label="Data type"><DataTypeSelect value={e.data_type} onChange={(v) => update({ data_type: v as TransportEntry["data_type"] })} /></Field>
      </div>
      <details className="mt-3 text-sm">
        <summary className="cursor-pointer text-slate-500 hover:text-forest-700">Advanced: fuel-based method, supplier factor, region</summary>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Actual fuel used" unit="litres" optional tip="If you have fuel receipts (e.g. a chartered bus), this overrides the distance method."><NumberInput value={e.fuel_litres} onChange={(v) => update({ fuel_litres: v, fuel_type: e.fuel_type || "diesel" })} /></Field>
          <Field label="Custom factor" unit="kg CO₂e per unit" optional><NumberInput value={e.custom_factor} onChange={(v) => update({ custom_factor: v, custom_factor_unit: e.custom_factor_unit || "passenger.km" })} /></Field>
          <Field label="Custom factor unit"><Select value={e.custom_factor_unit || "passenger.km"} onChange={(v) => update({ custom_factor_unit: v })} options={[{ value: "passenger.km", label: "per passenger-km" }, { value: "vehicle.km", label: "per vehicle-km" }]} /></Field>
          <Field label="Custom factor source" optional><input className="input" value={e.custom_factor_source ?? ""} onChange={(x) => update({ custom_factor_source: x.target.value })} /></Field>
          <Field label="Journey country (ISO)" optional tip="Defaults to the conference country. Selects road/rail factors."><input className="input uppercase" maxLength={2} value={e.region ?? ""} onChange={(x) => update({ region: x.target.value.toUpperCase() || null })} /></Field>
          {e.mode === "flight" && <div className="flex items-end pb-2"><Toggle checked={!!e.touches_uk} onChange={(v) => update({ touches_uk: v })} label="Flight to/from UK" /></div>}
        </div>
      </details>
      {(est.msg || est.err) && <p className={`mt-2 text-xs ${est.err ? "text-amber-700" : "text-forest-700"}`}>{est.err || `Estimated: ${est.msg}`}</p>}
      {pkm > 0 && <p className="mt-2 text-xs text-slate-500">{isVehicle ? `${((e.vehicles ?? e.passengers / (e.occupancy || 1)) * (e.distance_km || 0) * legs * e.trips).toLocaleString(undefined, { maximumFractionDigits: 0 })} vehicle-km` : `${pkm.toLocaleString(undefined, { maximumFractionDigits: 0 })} passenger-km`}{e.distance_source && e.distance_source !== "user" ? " · distance estimated" : ""}</p>}
    </div>
  );
}

export default function TransportForm() {
  const { input, setInput } = useConference();
  const [imp, setImp] = useState<{ busy: boolean; result?: Awaited<ReturnType<typeof api.importTransport>>; err?: string }>({ busy: false });
  const fileRef = useRef<HTMLInputElement>(null);
  const setList = (fn: (l: TransportEntry[]) => TransportEntry[]) => setInput((p) => ({ ...p, transport: fn(p.transport) }));
  const onFile = async (f: File) => {
    setImp({ busy: true });
    try { setImp({ busy: false, result: await api.importTransport(f, "return") }); } catch (x) { setImp({ busy: false, err: formatApiError(x) }); }
  };
  const addImported = () => {
    const rows = (imp.result?.entries || []).map((r) => { const { _row, ...rest } = r as Record<string, unknown>; void _row; return { ...rest, id: uid() } as unknown as TransportEntry; });
    setList((l) => [...l, ...rows]);
    setImp({ busy: false });
  };
  return (
    <div className="space-y-6">
      <Card title="Transportation" subtitle="Add each group of journeys to and from the conference (and local commutes). Usually the largest source of emissions." icon={<Plane size={20} />}
        actions={<div className="flex flex-wrap gap-2">
          <a className="btn-ghost" href={api.templateUrl} download><Download size={16} />CSV template</a>
          <button className="btn-secondary" onClick={() => fileRef.current?.click()} disabled={imp.busy}>{imp.busy ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}Upload CSV / Excel</button>
          <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = ""; }} />
        </div>}>
        <NotApplicable checked={input.transport_not_applicable} onChange={(v) => setInput((p) => ({ ...p, transport_not_applicable: v }))} what="Travel" />
        {imp.err && <div className="mt-3"><Alert kind="error">{imp.err}</Alert></div>}
        {imp.result && (
          <div className="mt-4 space-y-2 rounded-xl border border-slate-200 p-4">
            <p className="text-sm"><b>{imp.result.valid_rows}</b> valid of {imp.result.total_rows} rows · {imp.result.invalid_rows} invalid · {imp.result.duplicates} duplicates skipped</p>
            {imp.result.errors.length > 0 && (
              <ul className="max-h-40 overflow-auto text-xs text-red-700">{imp.result.errors.map((x) => <li key={x.row}>Row {x.row}: {x.message}</li>)}</ul>
            )}
            {imp.result.warnings.length > 0 && <ul className="text-xs text-amber-700">{imp.result.warnings.map((x) => <li key={x.row}>Row {x.row}: {x.message}</li>)}</ul>}
            <div className="flex gap-2"><button className="btn-primary" onClick={addImported} disabled={!imp.result.valid_rows}>Add {imp.result.valid_rows} journeys</button>
              <button className="btn-ghost" onClick={() => setImp({ busy: false })}>Cancel</button></div>
          </div>
        )}
      </Card>
      {!input.transport_not_applicable && (
        <>
          {input.transport.length > 30 && <Alert kind="info">{input.transport.length} journeys entered.</Alert>}
          <div className="space-y-4">
            {input.transport.map((e) => (
              <EntryCard key={e.id} e={e} update={(p) => setList((l) => l.map((x) => (x.id === e.id ? { ...x, ...p } : x)))}
                remove={() => setList((l) => l.filter((x) => x.id !== e.id))} />
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            {MODES.slice(0, 6).map((m) => (
              <button key={m.v} className="btn-secondary" onClick={() => setList((l) => [...l, newEntry(m.v)])}><Plus size={14} />{m.l}</button>
            ))}
            <button className="btn-secondary" onClick={() => setList((l) => [...l, newEntry("autorickshaw")])}><Plus size={14} />More…</button>
          </div>
          {input.transport.length === 0 && <Alert kind="warning">No journeys yet. If left empty, transportation will be reported as <b>not reported</b> (not zero).</Alert>}
        </>
      )}
    </div>
  );
}
