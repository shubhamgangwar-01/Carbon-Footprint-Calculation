/* Chart components. Palette: validated categorical slots (light mode) - see README "Chart colours".
   Light-mode contrast for some slots is < 3:1, so every chart carries a legend or direct labels and a table view. */
import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { CalcResult, Scenario } from "../types";
import { CATEGORY_META, fmt } from "../utils/format";

const tip = { contentStyle: { borderRadius: 12, border: "1px solid #e2e8f0", fontSize: 12 }, cursor: { fill: "rgba(15,23,42,0.04)" } };
const axis = { tick: { fontSize: 11, fill: "#64748b" }, axisLine: false, tickLine: false } as const;

export function CategoryDonut({ result }: { result: CalcResult }) {
  const data = result.by_category.filter((c) => c.emissions_kg > 0).map((c) => ({ name: CATEGORY_META[c.category].label, key: c.category, value: c.emissions_kg / 1000, share: c.share_pct }));
  return (
    <div className="relative h-72">
      <ResponsiveContainer>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" innerRadius="58%" outerRadius="85%" paddingAngle={1} stroke="#fff" strokeWidth={2} isAnimationActive={false}>
            {data.map((d) => <Cell key={d.key} fill={CATEGORY_META[d.key].color} />)}
          </Pie>
          <Tooltip {...tip} formatter={(v: number, _n, p) => [`${fmt(v, 2)} t CO₂e (${(p.payload as { share: number }).share.toFixed(1)}%)`, (p.payload as { name: string }).name]} />
          <Legend verticalAlign="bottom" iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12 }} formatter={(v, e) => <span className="text-slate-600">{v} · {((e.payload as unknown as { share: number }).share).toFixed(1)}%</span>} />
        </PieChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-x-0 top-[38%] -translate-y-1/2 text-center">
        <div className="text-2xl font-bold text-slate-900">{fmt(result.total_tonnes, 1)}</div>
        <div className="text-xs text-slate-500">t CO₂e</div>
      </div>
    </div>
  );
}

export function CategoryBars({ result }: { result: CalcResult }) {
  const data = result.by_category.map((c) => ({ name: CATEGORY_META[c.category].short, key: c.category, t: c.emissions_kg / 1000, status: c.status }));
  return (
    <div className="h-72">
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 16, right: 8, left: 0, bottom: 0 }} barCategoryGap="30%">
          <CartesianGrid vertical={false} stroke="#eef2f7" />
          <XAxis dataKey="name" {...axis} interval={0} />
          <YAxis {...axis} width={48} tickFormatter={(v) => fmt(v, v < 10 ? 1 : 0)} label={{ value: "t CO₂e", angle: -90, position: "insideLeft", fontSize: 11, fill: "#64748b" }} />
          <Tooltip {...tip} formatter={(v: number, _n, p) => [`${fmt(v, 3)} t CO₂e`, (p.payload as { status: string }).status.replace(/_/g, " ")]} />
          <Bar dataKey="t" radius={[4, 4, 0, 0]} isAnimationActive={false} label={{ position: "top", fontSize: 11, fill: "#334155", formatter: (v: number) => (v > 0 ? fmt(v, v < 10 ? 2 : 1) : "") }}>
            {data.map((d) => <Cell key={d.key} fill={CATEGORY_META[d.key].color} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function TopActivities({ result }: { result: CalcResult }) {
  const data = result.top_activities.slice(0, 8).map((a) => ({ name: a.activity.length > 34 ? a.activity.slice(0, 33) + "…" : a.activity, full: a.activity, t: a.emissions_kg / 1000, key: a.category, share: a.share_pct }));
  return (
    <div style={{ height: Math.max(180, data.length * 38 + 30) }}>
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 56, left: 8, bottom: 4 }} barCategoryGap="22%">
          <CartesianGrid horizontal={false} stroke="#eef2f7" />
          <XAxis type="number" {...axis} tickFormatter={(v) => fmt(v, v < 10 ? 1 : 0)} />
          <YAxis type="category" dataKey="name" {...axis} width={190} />
          <Tooltip {...tip} formatter={(v: number, _n, p) => [`${fmt(v, 3)} t CO₂e (${(p.payload as { share: number }).share.toFixed(1)}%)`, (p.payload as { full: string }).full]} labelFormatter={() => ""} />
          <Bar dataKey="t" radius={[0, 4, 4, 0]} isAnimationActive={false} label={{ position: "right", fontSize: 11, fill: "#334155", formatter: (v: number) => fmt(v, 2) }}>
            {data.map((d, i) => <Cell key={i} fill={CATEGORY_META[d.key].color} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function DataTypeBar({ result }: { result: CalcResult }) {
  const order = [["actual", "#1d5d3a"], ["estimated", "#5bb07a"], ["default", "#bbe3c6"]] as const;
  return (
    <div>
      <div className="flex h-4 w-full gap-0.5 overflow-hidden rounded-full bg-slate-100" role="img" aria-label="Share of emissions by activity data type">
        {order.map(([k, c]) => result.data_type_breakdown[k].share_pct > 0 && (
          <div key={k} title={`${k}: ${result.data_type_breakdown[k].share_pct.toFixed(1)}%`} style={{ width: `${result.data_type_breakdown[k].share_pct}%`, background: c }} />
        ))}
      </div>
      <ul className="mt-3 grid grid-cols-3 gap-2 text-xs text-slate-600">
        {order.map(([k, c]) => (
          <li key={k} className="flex items-start gap-1.5"><span className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: c }} />
            <span><span className="font-medium capitalize text-slate-800">{k}</span><br />{result.data_type_breakdown[k].share_pct.toFixed(1)}% · {fmt(result.data_type_breakdown[k].emissions_kg / 1000, 2)} t</span></li>
        ))}
      </ul>
    </div>
  );
}

export function ScenarioBars({ scenarios, basis = "location" }: { scenarios: Scenario[]; basis?: "location" | "market" }) {
  const data = scenarios.filter((s) => s.applicable && !s.error)
    .map((s) => ({ name: s.title.length > 40 ? s.title.slice(0, 39) + "…" : s.title, full: s.title, red: (basis === "market" ? s.market_reduction_kg : s.reduction_kg) / 1000,
      pct: basis === "market" ? s.market_reduction_pct : s.reduction_pct }))
    .sort((a, b) => b.red - a.red);
  if (!data.length) return <p className="text-sm text-slate-500">No applicable scenarios for the data entered.</p>;
  return (
    <div style={{ height: data.length * 40 + 40 }}>
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 80, left: 8, bottom: 4 }} barCategoryGap="22%">
          <CartesianGrid horizontal={false} stroke="#eef2f7" />
          <XAxis type="number" {...axis} tickFormatter={(v) => fmt(v, 1)} />
          <YAxis type="category" dataKey="name" {...axis} width={230} />
          <Tooltip {...tip} formatter={(v: number, _n, p) => [`${fmt(v, 3)} t CO₂e (${(p.payload as { pct: number }).pct.toFixed(1)}%)`, v >= 0 ? "Reduction" : "Increase"]} labelFormatter={(_l, p) => (p?.[0]?.payload as { full: string } | undefined)?.full ?? ""} />
          <Bar dataKey="red" radius={[0, 4, 4, 0]} isAnimationActive={false} label={{ position: "right", fontSize: 11, fill: "#334155", formatter: (v: number) => `${v >= 0 ? "−" : "+"}${fmt(Math.abs(v), 2)}\u00a0t` }}>
            {data.map((d, i) => <Cell key={i} fill={d.red >= 0 ? "#2a78d6" : "#94a3b8"} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ComparisonBars({ s }: { s: Scenario }) {
  const cats = Object.keys(CATEGORY_META);
  const data = cats.map((c) => ({ name: CATEGORY_META[c].short, Baseline: (s.baseline_by_category[c] || 0) / 1000, Scenario: (s.scenario_by_category[c] || 0) / 1000 }))
    .filter((d) => d.Baseline > 0 || d.Scenario > 0);
  return (
    <div className="h-64">
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} barGap={2} barCategoryGap="28%">
          <CartesianGrid vertical={false} stroke="#eef2f7" />
          <XAxis dataKey="name" {...axis} interval={0} />
          <YAxis {...axis} width={48} tickFormatter={(v) => fmt(v, v < 10 ? 1 : 0)} />
          <Tooltip {...tip} formatter={(v: number) => `${fmt(v, 3)} t CO₂e`} />
          <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12 }} />
          <Bar dataKey="Baseline" fill="#94a3b8" radius={[4, 4, 0, 0]} isAnimationActive={false} />
          <Bar dataKey="Scenario" fill="#2a78d6" radius={[4, 4, 0, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
