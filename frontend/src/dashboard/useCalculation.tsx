import { BarChart3, FileDown, FlaskConical, Pencil } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { api, formatApiError } from "../services/api";
import { useConference } from "../state/ConferenceContext";
import type { Calculation } from "../types";

export function useCalculation(calcId: number) {
  const [calc, setCalc] = useState<Calculation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const reload = () => api.getCalculation(calcId).then(setCalc).catch((e) => setError(formatApiError(e)));
  useEffect(() => { setCalc(null); reload(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [calcId]);
  return { calc, error, reload, setCalc };
}

export function ResultsHeader({ calc }: { calc: Calculation }) {
  const { load } = useConference();
  const nav = useNavigate();
  const tab = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium ${isActive ? "bg-forest-700 text-white" : "text-slate-600 hover:bg-slate-100"}`;
  const edit = async () => { await load(calc.conference_id); nav("/calculator/basic"); };
  return (
    <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div>
        <Link to="/conferences" className="text-sm text-slate-500 hover:text-forest-700">← My conferences</Link>
        <h1 className="mt-1 text-2xl font-bold text-slate-900">{calc.result.conference_name}</h1>
        <p className="text-sm text-slate-500">Calculation #{calc.id} · {new Date(calc.created_at).toLocaleString()} · factor set {calc.result.factor_set_version} · engine {calc.result.engine_version}</p>
      </div>
      <div className="flex flex-wrap gap-1 rounded-xl border border-slate-200 bg-white p-1">
        <NavLink end to={`/results/${calc.id}`} className={tab}><BarChart3 size={15} />Dashboard</NavLink>
        <NavLink to={`/results/${calc.id}/what-if`} className={tab}><FlaskConical size={15} />What-if</NavLink>
        <NavLink to={`/results/${calc.id}/report`} className={tab}><FileDown size={15} />Report</NavLink>
        <button onClick={edit} className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100"><Pencil size={15} />Edit data</button>
      </div>
    </div>
  );
}
