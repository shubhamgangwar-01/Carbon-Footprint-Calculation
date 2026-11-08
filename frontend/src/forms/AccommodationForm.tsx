import { BedDouble, Plus, Trash2 } from "lucide-react";
import { Alert, Card, DataTypeSelect, Field, NotApplicable, NumberInput, Select } from "../components/ui";
import { useConference } from "../state/ConferenceContext";
import type { AccommodationEntry } from "../types";
import { uid } from "../utils/format";

export default function AccommodationForm() {
  const { input, setInput, options } = useConference();
  const list = input.accommodation;
  const setList = (fn: (l: AccommodationEntry[]) => AccommodationEntry[]) => setInput((p) => ({ ...p, accommodation: fn(p.accommodation) }));
  const upd = (id: string, patch: Partial<AccommodationEntry>) => setList((l) => l.map((x) => (x.id === id ? { ...x, ...patch } : x)));
  const countries = options?.hotel_countries || [{ country: "India", factor: 58.9, key: "accommodation.hotel.india" }];
  return (
    <div className="space-y-6">
      <Card title="Accommodation" icon={<BedDouble size={20} />}
        subtitle="Hotel nights for participants. Priority: actual hotel energy data → hotel-specific factor → published country benchmark (Cornell CHSB via DESNZ).">
        <NotApplicable checked={input.accommodation_not_applicable} onChange={(v) => setInput((p) => ({ ...p, accommodation_not_applicable: v }))} what="Overnight accommodation" />
      </Card>
      {!input.accommodation_not_applicable && list.map((a) => {
        const f = countries.find((c) => c.country === a.country);
        const roomNights = (a.rooms ?? (a.guests ?? 0) / (a.guests_per_room || 1)) * a.nights;
        return (
          <div key={a.id} className="card p-5">
            <div className="mb-3 flex items-center gap-3">
              <input className="input max-w-sm" placeholder="Label e.g. Partner hotel block" value={a.label ?? ""} onChange={(e) => upd(a.id, { label: e.target.value })} />
              <button className="btn-ghost ml-auto text-red-600" aria-label="Remove" onClick={() => setList((l) => l.filter((x) => x.id !== a.id))}><Trash2 size={16} /></button>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Field label="Hotel country" tip="Country-level median of hotels in the Cornell Hotel Sustainability Benchmarking Index (2021), as published by DESNZ.">
                <Select value={a.country} onChange={(v) => upd(a.id, { country: v })} options={countries.map((c) => ({ value: c.country, label: `${c.country} (${c.factor} kg/room-night)` }))} />
              </Field>
              <Field label="Hotel name" optional><input className="input" value={a.hotel_name ?? ""} onChange={(e) => upd(a.id, { hotel_name: e.target.value })} /></Field>
              <Field label="Rooms booked" tip="Preferred. If unknown, enter guests (and guests per room)."><NumberInput value={a.rooms} step="1" onChange={(v) => upd(a.id, { rooms: v })} /></Field>
              <Field label="Nights" unit="nights"><NumberInput value={a.nights} step="1" onChange={(v) => upd(a.id, { nights: v ?? 0 })} /></Field>
              <Field label="Guests staying overnight" optional><NumberInput value={a.guests} step="1" onChange={(v) => upd(a.id, { guests: v })} /></Field>
              <Field label="Guests per room" optional tip="Used only when rooms are not given. If unknown, 1 guest per room is assumed (conservative)."><NumberInput value={a.guests_per_room} min={1} onChange={(v) => upd(a.id, { guests_per_room: v })} /></Field>
              <Field label="Accommodation type" tip="Recorded for context. No class-specific (luxury/budget) factors are published, so none are invented.">
                <Select value={a.accommodation_type ?? "hotel"} onChange={(v) => upd(a.id, { accommodation_type: v })} options={[{ value: "hotel", label: "Hotel" }, { value: "guest_house", label: "Guest house / hostel" }, { value: "serviced_apartment", label: "Serviced apartment" }, { value: "campus", label: "Campus accommodation" }]} />
              </Field>
              <Field label="Data type"><DataTypeSelect value={a.data_type} onChange={(v) => upd(a.id, { data_type: v as AccommodationEntry["data_type"] })} /></Field>
            </div>
            <details className="mt-3 text-sm">
              <summary className="cursor-pointer text-slate-500 hover:text-forest-700">Hotel-supplied data (more accurate)</summary>
              <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <Field label="Hotel factor" unit="kg CO₂e/room-night" optional tip="From the hotel's sustainability report or HCMI calculation."><NumberInput value={a.hotel_factor_kg_per_room_night} onChange={(v) => upd(a.id, { hotel_factor_kg_per_room_night: v })} /></Field>
                <Field label="Factor source" optional><input className="input" value={a.hotel_factor_source ?? ""} onChange={(e) => upd(a.id, { hotel_factor_source: e.target.value })} /></Field>
                <Field label="Actual electricity" unit="kWh" optional tip="Energy attributable to the conference's rooms. If given, this replaces the room-night method."><NumberInput value={a.electricity_kwh} onChange={(v) => upd(a.id, { electricity_kwh: v })} /></Field>
                <Field label="Diesel" unit="litres" optional><NumberInput value={a.diesel_litres} onChange={(v) => upd(a.id, { diesel_litres: v })} /></Field>
                <Field label="LPG" unit="kg" optional><NumberInput value={a.lpg_kg} onChange={(v) => upd(a.id, { lpg_kg: v })} /></Field>
              </div>
            </details>
            {roomNights > 0 && !a.electricity_kwh && (
              <p className="mt-3 text-xs text-slate-500">{roomNights.toLocaleString(undefined, { maximumFractionDigits: 1 })} room-nights × {a.hotel_factor_kg_per_room_night ?? f?.factor ?? "?"} kg = {(roomNights * (a.hotel_factor_kg_per_room_night ?? f?.factor ?? 0)).toLocaleString(undefined, { maximumFractionDigits: 0 })} kg CO₂e</p>
            )}
          </div>
        );
      })}
      {!input.accommodation_not_applicable && (
        <>
          <button className="btn-secondary" onClick={() => setList((l) => [...l, { id: uid(), country: input.basic.country === "United Kingdom" ? "UK" : input.basic.country, nights: Math.max((input.basic.days || 1) - 1, 1), rooms: null, data_type: "actual", accommodation_type: "hotel" }])}>
            <Plus size={14} />Add accommodation
          </button>
          {list.length === 0 && <Alert kind="warning">No accommodation entered - it will be reported as <b>not reported</b>. Tick “does not apply” for a local one-day event.</Alert>}
        </>
      )}
    </div>
  );
}
