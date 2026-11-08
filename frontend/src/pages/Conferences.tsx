import { BarChart3, Pencil, Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Alert, Card, Spinner } from "../components/ui";
import { api, currentUser, formatApiError, type ConferenceSummary } from "../services/api";
import { useConference } from "../state/ConferenceContext";
import { fmt } from "../utils/format";

export default function Conferences() {
  const [rows, setRows] = useState<ConferenceSummary[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const { load, reset } = useConference();
  const nav = useNavigate();
  const refresh = () => api.listConferences().then(setRows).catch((e) => setErr(formatApiError(e)));
  useEffect(() => { refresh(); }, []);
  const user = currentUser();
  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div><h1 className="text-2xl font-bold">My conferences</h1>
          <p className="text-sm text-slate-500">{user?.role === "guest" ? <>Guest session on this device. <Link to="/login" className="text-forest-700 underline">Create an account</Link> to keep your conferences.</> : `Signed in as ${user?.email}`}</p></div>
        <button className="btn-primary" onClick={() => { reset(); nav("/calculator/basic"); }}><Plus size={16} />New conference</button>
      </div>
      {err && <Alert kind="error">{err}</Alert>}
      {!rows ? <Spinner /> : rows.length === 0 ? <Card><p className="text-sm text-slate-500">No conferences yet.</p></Card> : (
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[720px]">
            <thead className="bg-slate-50"><tr><th className="th">Conference</th><th className="th">Dates</th><th className="th">Format</th><th className="th text-right">Latest footprint</th><th className="th text-right">Actions</th></tr></thead>
            <tbody>{rows.map((c) => (
              <tr key={c.id} className="border-t border-slate-100">
                <td className="td"><div className="font-medium text-slate-900">{c.name}</div><div className="text-xs text-slate-500">{[c.state_city, c.country].filter(Boolean).join(", ")}{c.is_sample && <span className="chip ml-2 bg-violet-50 text-violet-700">sample</span>}</div></td>
                <td className="td text-sm text-slate-600">{c.start_date ? `${c.start_date} → ${c.end_date}` : `${c.days} day(s)`}</td>
                <td className="td text-sm capitalize">{c.format}</td>
                <td className="td text-right">{c.latest_calculation ? <><b>{fmt(c.latest_calculation.total_kg / 1000, 2)} t</b><div className="text-xs text-slate-500">{new Date(c.latest_calculation.created_at).toLocaleDateString()}</div></> : <span className="text-sm text-slate-400">not calculated</span>}</td>
                <td className="td"><div className="flex justify-end gap-1">
                  {c.latest_calculation && <Link className="btn-ghost px-2" to={`/results/${c.latest_calculation.id}`} aria-label="Results"><BarChart3 size={16} /></Link>}
                  <button className="btn-ghost px-2" aria-label="Edit" onClick={async () => { await load(c.id); nav("/calculator/basic"); }}><Pencil size={16} /></button>
                  <button className="btn-ghost px-2 text-red-600" aria-label="Delete" onClick={async () => { if (window.confirm(`Delete "${c.name}"?`)) { await api.deleteConference(c.id); refresh(); } }}><Trash2 size={16} /></button>
                </div></td>
              </tr>))}</tbody>
          </table>
        </div>
      )}
    </div>
  );
}
