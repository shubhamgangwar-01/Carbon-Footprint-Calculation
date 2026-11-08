import { BookOpen, Database, ExternalLink, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { Card, DQChip, Select, Spinner } from "../components/ui";
import { api } from "../services/api";

export default function Methodology() {
  const [factors, setFactors] = useState<Record<string, any>[] | null>(null);
  const [sources, setSources] = useState<Record<string, any>[]>([]);
  const [cat, setCat] = useState("");
  const [q, setQ] = useState("");
  useEffect(() => { api.sources().then(setSources).catch(() => null); }, []);
  useEffect(() => { const t = setTimeout(() => api.factors({ category: cat || undefined, q: q || undefined }).then(setFactors).catch(() => setFactors([])), 250); return () => clearTimeout(t); }, [cat, q]);
  return (
    <div className="mx-auto max-w-7xl space-y-6 px-4 py-8 sm:px-6">
      <div><h1 className="text-2xl font-bold">Methodology & data</h1><p className="text-sm text-slate-500">How the footprint is calculated and where every number comes from.</p></div>
      <Card title="Calculation approach" icon={<BookOpen size={20} />}>
        <div className="grid gap-6 text-sm text-slate-700 md:grid-cols-2">
          <div className="space-y-2">
            <p><b>Core rule:</b> emissions (kg CO₂e) = activity data × emission factor, summed over all activities; tonnes = kg ÷ 1,000.</p>
            <p><b>Standards:</b> GHG Protocol Corporate Standard, Scope 2 Guidance (location- and market-based electricity), Scope 3 Standard (categories 1, 5, 6, 7) and ISO 14064-1 principles - relevance, completeness, consistency, accuracy, transparency.</p>
            <p><b>GWP:</b> IPCC AR5 100-year (CH₄ = 28, N₂O = 265), matching DESNZ 2026.</p>
            <p><b>India first:</b> CEA grid factor (FY 2025-26: 0.675 kg CO₂/kWh → 0.678 kg CO₂e/kWh), India GHG Program road & rail factors, CHSB India hotel benchmark (58.9 kg/room-night), NIN-based meal composition. International proxies are flagged.</p>
          </div>
          <ul className="list-disc space-y-1 pl-5">
            <li><b>Flights:</b> passenger-km × DESNZ factor by haul and cabin class, 8% routing uplift built in, optional radiative forcing (×1.7 on CO₂).</li>
            <li><b>Road vehicles:</b> vehicle-km = passengers ÷ occupancy × distance × legs × trips (no passenger double counting).</li>
            <li><b>Public transport:</b> passenger-km × per-passenger factor.</li>
            <li><b>Electricity:</b> metered kWh × grid factor; equipment-load estimates only if no meter reading.</li>
            <li><b>Food:</b> meal counts × modelled per-meal factor <i>or</i> ingredient kg × Poore & Nemecek factor - mutually exclusive per meal.</li>
            <li><b>Waste:</b> kg × route factor (cut-off method, no recycling credits). Unassigned waste → landfill (flagged).</li>
            <li><b>Missing data</b> is reported as “not reported/incomplete”, never as zero. <b>Offsets</b> are never netted from gross.</li>
          </ul>
        </div>
      </Card>
      <Card title="Data sources" subtitle="Original files were downloaded, checksummed and kept unmodified in data/raw/." icon={<Database size={20} />}>
        <div className="overflow-x-auto"><table className="w-full min-w-[800px] text-sm">
          <thead className="bg-slate-50"><tr><th className="th">Source</th><th className="th">Version / year</th><th className="th">Geography</th><th className="th">Licence</th><th className="th">Status</th></tr></thead>
          <tbody>{sources.map((s) => (
            <tr key={s.source_id} className="border-t border-slate-100">
              <td className="td"><a href={s.landing_page || s.url} target="_blank" rel="noreferrer" className="font-medium text-forest-800 hover:underline">{s.name}<ExternalLink size={12} className="ml-1 inline" /></a><div className="text-xs text-slate-500">{s.publisher}</div></td>
              <td className="td text-xs">{s.version}<div className="text-slate-400">{s.reporting_year}</div></td>
              <td className="td text-xs">{s.geography}</td><td className="td max-w-[200px] text-xs text-slate-500">{s.licence}</td>
              <td className="td"><span className={`chip ${s.status === "downloaded" ? "bg-forest-100 text-forest-800" : s.status === "failed" ? "bg-red-50 text-red-700" : "bg-slate-100 text-slate-600"}`}>{s.status}</span></td>
            </tr>))}</tbody></table></div>
      </Card>
      <Card title="Emission factor browser" subtitle={factors ? `${factors.length} active factors` : ""}
        actions={<div className="flex flex-wrap gap-2">
          <div className="relative"><Search size={14} className="absolute left-2.5 top-3 text-slate-400" /><input className="input pl-8" placeholder="Search…" value={q} onChange={(e) => setQ(e.target.value)} /></div>
          <div className="w-44"><Select value={cat} onChange={setCat} options={[{ value: "", label: "All categories" }, ...["transportation", "accommodation", "energy", "food", "waste", "materials", "parameter"].map((c) => ({ value: c, label: c }))]} /></div>
        </div>}>
        {!factors ? <Spinner /> : (
          <div className="max-h-[600px] overflow-auto"><table className="w-full min-w-[900px] text-sm">
            <thead className="sticky top-0 bg-slate-50"><tr><th className="th">Factor</th><th className="th text-right">Value</th><th className="th">Source</th><th className="th">Boundary</th><th className="th">Quality</th></tr></thead>
            <tbody>{factors.map((f) => (
              <tr key={f.factor_id} className="border-t border-slate-100">
                <td className="td"><div className="font-medium">{f.subcategory}</div><div className="font-mono text-[10px] text-slate-400">{f.factor_id}</div></td>
                <td className="td text-right tabular-nums">{Number(f.emission_factor).toPrecision(4)}<div className="text-[11px] text-slate-400">{f.unit}</div></td>
                <td className="td max-w-[240px] text-xs">{f.source_name}<div className="text-slate-400">{f.reporting_year} · {f.geography}</div></td>
                <td className="td max-w-[320px] text-xs text-slate-500">{f.system_boundary}</td>
                <td className="td"><DQChip q={f.data_quality?.label || "medium"} /></td>
              </tr>))}</tbody></table></div>
        )}
      </Card>
    </div>
  );
}
