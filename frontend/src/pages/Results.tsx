import { AlertTriangle, ArrowDownRight, CalendarDays, Gauge, Leaf, Lightbulb, Table2, Users } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { CategoryBars, CategoryDonut, DataTypeBar, TopActivities } from "../charts/Charts";
import { Alert, Card, DQChip, DTChip, Select, Spinner, StatusChip } from "../components/ui";
import { ResultsHeader, useCalculation } from "../dashboard/useCalculation";
import { CATEGORY_META, fmt, fmtKg } from "../utils/format";

function Kpi({ icon, label, value, unit, sub }: { icon: React.ReactNode; label: string; value: string; unit: string; sub?: string }) {
  return (
    <div className="card p-5">
      <div className="flex items-center gap-2 text-sm font-medium text-slate-500"><span className="rounded-lg bg-mint-100 p-1.5 text-forest-700">{icon}</span>{label}</div>
      <div className="mt-3 text-3xl font-bold tracking-tight text-slate-900">{value} <span className="text-base font-medium text-slate-500">{unit}</span></div>
      {sub && <div className="mt-1 text-xs text-slate-500">{sub}</div>}
    </div>
  );
}

export default function Results() {
  const { calcId } = useParams();
  const { calc, error } = useCalculation(Number(calcId));
  const [cat, setCat] = useState("all");
  const [view, setView] = useState<"chart" | "table">("chart");
  const lines = useMemo(() => (calc ? calc.result.lines.filter((l) => cat === "all" || l.category === cat) : []), [calc, cat]);
  if (error) return <div className="mx-auto max-w-3xl p-6"><Alert kind="error">{error}</Alert></div>;
  if (!calc) return <Spinner label="Loading results…" />;
  const r = calc.result;
  const issues = r.issues.filter((i) => i.level !== "info");
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <ResultsHeader calc={calc} />
      {!r.completeness.is_complete && (
        <div className="mb-6"><Alert kind="warning">
          <b>Incomplete footprint.</b> {r.completeness.categories_not_reported.length > 0 && <>Not reported: {r.completeness.categories_not_reported.map((c) => CATEGORY_META[c].label).join(", ")}. </>}
          {r.completeness.categories_incomplete.length > 0 && <>Incomplete: {r.completeness.categories_incomplete.map((c) => CATEGORY_META[c].label).join(", ")}. </>}
          Missing data is not counted as zero - see data issues below.
        </Alert></div>
      )}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi icon={<Leaf size={16} />} label="Total footprint" value={fmt(r.total_tonnes, 2)} unit="t CO₂e" sub={`${fmt(r.total_kg, 0)} kg CO₂e · gross, location-based`} />
        <Kpi icon={<Users size={16} />} label="Per participant" value={fmt(r.per_participant_kg, 1)} unit="kg CO₂e" sub={`${r.participants.toLocaleString()} in-person participants`} />
        <Kpi icon={<CalendarDays size={16} />} label="Per conference day" value={fmt((r.per_day_kg || 0) / 1000, 2)} unit="t CO₂e" sub={`${r.days} day(s) · ${fmt(r.per_participant_day_kg, 1)} kg per participant-day`} />
        <Kpi icon={<Gauge size={16} />} label="Data quality" value={(r.data_quality.label || "n/a").replace(/^./, (c) => c.toUpperCase())} unit={`score ${r.data_quality.weighted_score ?? "–"}`}
          sub={`Uncertainty: ${r.data_quality.uncertainty_rating} · ${r.data_quality.proxy_factor_share_pct}% via proxy factors`} />
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-3">
        <div className="card p-4 text-sm"><div className="text-slate-500">Market-based total</div><div className="text-lg font-semibold">{fmt(r.total_market_based_kg / 1000, 2)} t CO₂e</div><div className="text-xs text-slate-500">Renewable certificates applied to electricity</div></div>
        <div className="card p-4 text-sm"><div className="text-slate-500">Offsets retired (separate)</div><div className="text-lg font-semibold">{fmt(r.offsets_tonnes, 2)} t CO₂e</div><div className="text-xs text-slate-500">Never deducted from gross emissions</div></div>
        <div className="card p-4 text-sm"><div className="text-slate-500">Gross minus offsets</div><div className="text-lg font-semibold">{fmt(r.net_tonnes_after_offsets, 2)} t CO₂e</div><div className="text-xs text-slate-500">Shown for information only</div></div>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-5">
        <Card title="Emissions by category" className="lg:col-span-2"
          actions={<button className="btn-ghost px-2 py-1 text-xs" onClick={() => setView(view === "chart" ? "table" : "chart")}><Table2 size={14} />{view === "chart" ? "Table" : "Chart"}</button>}>
          {view === "chart" ? <CategoryDonut result={r} /> : (
            <table className="w-full text-sm"><thead><tr><th className="th">Category</th><th className="th text-right">t CO₂e</th><th className="th text-right">Share</th></tr></thead>
              <tbody>{r.by_category.map((c) => <tr key={c.category} className="border-t border-slate-100"><td className="td">{c.label}</td><td className="td text-right">{fmt(c.emissions_kg / 1000, 3)}</td><td className="td text-right">{c.share_pct.toFixed(1)}%</td></tr>)}</tbody></table>
          )}
        </Card>
        <Card title="Category-wise emissions" subtitle="t CO₂e and reporting status" className="lg:col-span-3">
          <CategoryBars result={r} />
          <div className="mt-2 flex flex-wrap gap-2">{r.by_category.map((c) => <span key={c.category} className="flex items-center gap-1 text-xs text-slate-600"><span className="h-2 w-2 rounded-full" style={{ background: CATEGORY_META[c.category].color }} />{CATEGORY_META[c.category].short}<StatusChip status={c.status} /></span>)}</div>
        </Card>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-5">
        <Card title="Highest-emission activities" subtitle="t CO₂e" className="lg:col-span-3"><TopActivities result={r} /></Card>
        <Card title="Actual vs. estimated data" subtitle="Share of emissions by type of activity data" className="lg:col-span-2">
          <DataTypeBar result={r} />
          <div className="mt-5 border-t border-slate-100 pt-4 text-xs text-slate-600">
            <p><b>Data quality</b> is the emissions-weighted pedigree score of the factors used (1 = best, 5 = worst), based on geographical, temporal and technological representativeness and source reliability.</p>
            <div className="mt-2 flex flex-wrap gap-2">{Object.entries(r.data_quality.emissions_by_factor_quality_kg).map(([k, v]) => <span key={k} className="flex items-center gap-1"><DQChip q={k} />{fmt(v / 1000, 2)} t</span>)}</div>
          </div>
        </Card>
      </div>

      <Card title="Reduction opportunities" subtitle="Generated from this conference's breakdown and quantified with the same factors" icon={<Lightbulb size={20} />} className="mt-6"
        actions={<Link to={`/results/${calc.id}/what-if`} className="btn-secondary">Explore what-if scenarios</Link>}>
        <div className="grid gap-4 md:grid-cols-2">
          {calc.recommendations.map((rec) => (
            <div key={rec.rank} className="rounded-xl border border-slate-200 p-4">
              <div className="flex items-start justify-between gap-3">
                <div><div className="text-xs font-medium uppercase tracking-wide text-slate-500">{rec.category_label}</div><h3 className="font-semibold text-slate-900">{rec.rank}. {rec.title}</h3></div>
                {rec.potential_reduction_kg ? (
                  <span className="chip shrink-0 bg-forest-100 text-forest-800"><ArrowDownRight size={12} />{fmtKg(rec.potential_reduction_kg)} ({rec.potential_reduction_pct?.toFixed(1)}%)</span>
                ) : null}
              </div>
              <p className="mt-1 text-xs text-slate-500">{rec.evidence}{rec.potential_basis === "market-based" ? " Reduction shown on the market-based total." : ""}</p>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">{rec.actions.map((a) => <li key={a}>{a}</li>)}</ul>
            </div>
          ))}
          {calc.recommendations.length === 0 && <p className="text-sm text-slate-500">No recommendations - enter more activity data.</p>}
        </div>
      </Card>

      {issues.length > 0 && (
        <Card title="Data issues" icon={<AlertTriangle size={20} />} className="mt-6">
          <div className="space-y-2">{issues.map((i, k) => <Alert key={k} kind={i.level === "error" ? "error" : "warning"}><b>{CATEGORY_META[i.category]?.label || i.category}:</b> {i.message}</Alert>)}</div>
        </Card>
      )}

      <Card title="Detailed calculation table" subtitle="Every number is traceable to its activity data and emission factor" className="mt-6"
        actions={<div className="w-52"><Select ariaLabel="Filter category" value={cat} onChange={setCat} options={[{ value: "all", label: "All categories" }, ...Object.entries(CATEGORY_META).map(([k, v]) => ({ value: k, label: v.label }))]} /></div>}>
        <div className="-mx-5 overflow-x-auto sm:-mx-6">
          <table className="w-full min-w-[960px]">
            <thead className="bg-slate-50"><tr>
              <th className="th">Category / activity</th><th className="th text-right">Quantity</th><th className="th">Unit</th><th className="th text-right">Emission factor</th>
              <th className="th">Factor source</th><th className="th text-right">kg CO₂e</th><th className="th">Data</th></tr></thead>
            <tbody>
              {lines.map((l) => (
                <tr key={l.line_id} className="border-t border-slate-100 hover:bg-slate-50/60">
                  <td className="td"><div className="flex items-center gap-1.5 text-xs text-slate-500"><span className="h-2 w-2 rounded-full" style={{ background: CATEGORY_META[l.category].color }} />{CATEGORY_META[l.category].short} · {l.activity}</div>
                    <div className="font-medium text-slate-800">{l.description}</div><div className="font-mono text-[11px] text-slate-400">{l.formula}</div>
                    {l.notes.length > 0 && <details className="text-xs text-slate-500"><summary className="cursor-pointer">Notes ({l.notes.length})</summary><ul className="list-disc pl-4">{l.notes.map((n) => <li key={n}>{n}</li>)}</ul></details>}</td>
                  <td className="td text-right tabular-nums">{fmt(l.quantity, 2)}</td>
                  <td className="td text-xs text-slate-500">{l.quantity_unit}</td>
                  <td className="td text-right tabular-nums">{l.factor_value !== undefined && l.factor_value !== null ? <>{l.factor_value.toPrecision(4)}<div className="text-[11px] text-slate-400">{l.factor_unit}</div></> : "custom"}</td>
                  <td className="td max-w-[220px] text-xs text-slate-600">{l.factor_source}<div className="truncate font-mono text-[10px] text-slate-400" title={l.factor_id}>{l.factor_id}</div></td>
                  <td className="td text-right font-semibold tabular-nums">{fmt(l.emissions_kg, 2)}</td>
                  <td className="td"><div className="flex flex-col items-start gap-1"><DTChip t={l.data_type} /><DQChip q={l.data_quality} />{l.is_proxy && <span className="chip bg-violet-50 text-violet-700">proxy</span>}</div></td>
                </tr>
              ))}
            </tbody>
            <tfoot><tr className="border-t-2 border-slate-200 bg-slate-50"><td className="td font-semibold" colSpan={5}>Total {cat !== "all" ? `(${CATEGORY_META[cat].label})` : ""}</td>
              <td className="td text-right font-bold tabular-nums">{fmt(lines.reduce((s, l) => s + l.emissions_kg, 0), 2)}</td><td /></tr></tfoot>
          </table>
        </div>
      </Card>

      <div className="mt-6 grid gap-6 md:grid-cols-2">
        <Card title="Assumptions"><ul className="list-disc space-y-1 pl-5 text-sm text-slate-600">{r.assumptions.map((a) => <li key={a}>{a}</li>)}</ul></Card>
        <Card title="Exclusions"><ul className="list-disc space-y-1 pl-5 text-sm text-slate-600">{r.exclusions.map((a) => <li key={a}>{a}</li>)}</ul></Card>
      </div>
    </div>
  );
}
