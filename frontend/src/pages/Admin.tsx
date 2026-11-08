import { Plus, Shield } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Alert, Card, DQChip, Field, NumberInput, Select, Spinner } from "../components/ui";
import { api, currentUser, formatApiError } from "../services/api";
import { fmt } from "../utils/format";

const blank = { factor_key: "", category: "transportation", activity: "", subcategory: "", emission_factor: 0, activity_unit: "passenger.km",
  geography: "India", reporting_year: "2026", source_name: "", source_url: "", dataset_version: "", system_boundary: "", methodology: "",
  data_quality_label: "medium", activate: true };

export default function Admin() {
  const user = currentUser();
  const [stats, setStats] = useState<Record<string, number> | null>(null);
  const [calcs, setCalcs] = useState<Record<string, any>[]>([]);
  const [factors, setFactors] = useState<Record<string, any>[]>([]);
  const [q, setQ] = useState("");
  const [form, setForm] = useState({ ...blank });
  const [msg, setMsg] = useState<{ kind: "success" | "error"; text: string } | null>(null);
  const refresh = () => {
    api.adminStats().then(setStats).catch((e) => setMsg({ kind: "error", text: formatApiError(e) }));
    api.adminCalculations().then(setCalcs).catch(() => null);
  };
  useEffect(() => { if (user?.role === "admin") refresh(); }, []);
  useEffect(() => { if (q.length >= 2) api.factors({ q, include_inactive: true }).then(setFactors); else setFactors([]); }, [q]);
  if (user?.role !== "admin") return <div className="mx-auto max-w-xl p-8"><Alert kind="warning">Administrator access required. <Link to="/login" className="underline">Sign in</Link> with an admin account.</Alert></div>;
  const add = async () => {
    setMsg(null);
    try { const r = await api.adminAddFactor(form); setMsg({ kind: "success", text: `Added ${r.factor_id}${r.is_active ? " (active)" : ""}.` }); setForm({ ...blank }); refresh(); }
    catch (e) { setMsg({ kind: "error", text: formatApiError(e) }); }
  };
  const toggle = async (fid: string, active: boolean) => {
    try { await api.adminSetActive(fid, active); setFactors(await api.factors({ q, include_inactive: true })); refresh(); } catch (e) { setMsg({ kind: "error", text: formatApiError(e) }); }
  };
  const S = (k: keyof typeof blank, label: string, tip?: string) => (
    <Field label={label} tip={tip}><input className="input" value={String(form[k])} onChange={(e) => setForm({ ...form, [k]: e.target.value })} /></Field>
  );
  return (
    <div className="mx-auto max-w-7xl space-y-6 px-4 py-8 sm:px-6">
      <div className="flex items-center gap-2"><Shield className="text-forest-700" /><h1 className="text-2xl font-bold">Administration</h1></div>
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
      {!stats ? <Spinner /> : (
        <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-6">{Object.entries(stats).map(([k, v]) => <div key={k} className="card p-4"><div className="text-xs text-slate-500">{k.replace(/_/g, " ")}</div><div className="text-xl font-bold">{v}</div></div>)}</div>
      )}
      <Card title="Add factor or new factor version" subtitle="Versions are immutable: a new dataset_version creates a new record; activating it deactivates the previous version. Stored calculations keep their pinned factor ids.">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {S("factor_key", "Factor key", "e.g. accommodation.hotel.india - reuse an existing key to publish a new version")}
          <Field label="Category"><Select value={form.category} onChange={(v) => setForm({ ...form, category: v })} options={["transportation", "accommodation", "energy", "food", "waste", "materials"].map((c) => ({ value: c, label: c }))} /></Field>
          {S("activity", "Activity")}{S("subcategory", "Description")}
          <Field label="Emission factor" unit="kg CO₂e per unit"><NumberInput value={form.emission_factor} onChange={(v) => setForm({ ...form, emission_factor: v ?? 0 })} /></Field>
          {S("activity_unit", "Activity unit", "e.g. passenger.km, vehicle.km, kWh, kg, room.night, meal")}
          {S("geography", "Geography")}{S("reporting_year", "Reporting year")}
          {S("source_name", "Source name")}{S("source_url", "Source URL")}{S("dataset_version", "Dataset version")}
          <Field label="Data quality"><Select value={form.data_quality_label} onChange={(v) => setForm({ ...form, data_quality_label: v })} options={["high", "medium", "low"].map((c) => ({ value: c, label: c }))} /></Field>
          <div className="sm:col-span-2">{S("system_boundary", "System boundary")}</div>
          <div className="sm:col-span-2">{S("methodology", "Methodology")}</div>
        </div>
        <button className="btn-primary mt-4" onClick={add}><Plus size={16} />Add factor</button>
      </Card>
      <Card title="Find, activate or deactivate factors" actions={<input className="input w-64" placeholder="Search key / description…" value={q} onChange={(e) => setQ(e.target.value)} />}>
        <div className="max-h-96 overflow-auto"><table className="w-full min-w-[800px] text-sm">
          <thead className="sticky top-0 bg-slate-50"><tr><th className="th">Factor id</th><th className="th text-right">Value</th><th className="th">Version</th><th className="th">Quality</th><th className="th">Status</th></tr></thead>
          <tbody>{factors.map((f) => (
            <tr key={f.factor_id} className="border-t border-slate-100">
              <td className="td"><div className="font-mono text-xs">{f.factor_id}</div><div className="text-xs text-slate-500">{f.subcategory}</div></td>
              <td className="td text-right">{Number(f.emission_factor).toPrecision(4)} <span className="text-xs text-slate-400">{f.unit}</span></td>
              <td className="td text-xs">{f.dataset_version}{f.created_by && <div className="text-slate-400">by {f.created_by}</div>}</td>
              <td className="td"><DQChip q={f.data_quality?.label || "medium"} /></td>
              <td className="td"><button className={f.is_active ? "btn-secondary px-2 py-1 text-xs" : "btn-primary px-2 py-1 text-xs"} onClick={() => toggle(f.factor_id, !f.is_active)}>{f.is_active ? "Deactivate" : "Activate"}</button></td>
            </tr>))}</tbody></table></div>
      </Card>
      <Card title="Calculation history (all users)">
        <div className="max-h-96 overflow-auto"><table className="w-full text-sm">
          <thead className="sticky top-0 bg-slate-50"><tr><th className="th">#</th><th className="th">Conference</th><th className="th text-right">t CO₂e</th><th className="th">Factor set</th><th className="th">Date</th></tr></thead>
          <tbody>{calcs.map((c) => (
            <tr key={c.id} className="border-t border-slate-100"><td className="td"><Link to={`/results/${c.id}`} className="text-forest-700 hover:underline">{c.id}</Link></td><td className="td">{c.conference}</td>
              <td className="td text-right">{fmt(c.total_kg / 1000, 2)}</td><td className="td text-xs">{c.factor_set_version}</td><td className="td text-xs">{new Date(c.created_at).toLocaleString()}</td></tr>))}</tbody></table></div>
      </Card>
    </div>
  );
}
