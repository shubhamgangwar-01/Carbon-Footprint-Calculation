import { ArrowRight, BarChart3, BedDouble, Database, FileText, FlaskConical, Plane, Recycle, ShieldCheck, Sparkles, UtensilsCrossed, Zap } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, formatApiError } from "../services/api";
import { useConference } from "../state/ConferenceContext";
import { Alert } from "../components/ui";

export default function Landing() {
  const nav = useNavigate();
  const { reset, load } = useConference();
  const [samples, setSamples] = useState<{ id: string; title: string; description: string }[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api.samples().then(setSamples).catch(() => setSamples([])); }, []);

  const start = () => { reset(); nav("/calculator/basic"); };
  const openSample = async (id: string) => {
    setBusy(id); setErr(null);
    try {
      const c = await api.loadSample(id);
      await load(c.id);
      const calc = await api.calculate(c.id);
      nav(`/results/${calc.id}`);
    } catch (e) { setErr(formatApiError(e)); } finally { setBusy(null); }
  };

  const modules = [
    { icon: Plane, t: "Transport", d: "Flights by haul & cabin class (with radiative forcing), rail, bus, car, taxi, two/three-wheelers, EVs, CSV bulk upload." },
    { icon: BedDouble, t: "Accommodation", d: "Room-nights with country benchmarks (CHSB), hotel-specific factors or actual hotel energy." },
    { icon: Zap, t: "Venue energy", d: "Metered grid electricity (CEA India grid factor), renewables, generators and fuels - no double counting." },
    { icon: UtensilsCrossed, t: "Food & beverages", d: "Meal-based or ingredient-based catering, bottled water, using Poore & Nemecek life-cycle data." },
    { icon: Recycle, t: "Waste", d: "By material and disposal route - landfill, recycling, composting, incineration, anaerobic digestion." },
    { icon: FileText, t: "Materials", d: "Printed pages, banners, ID cards, lanyards, kits - with reuse over multiple events." },
  ];
  return (
    <div>
      <section className="bg-gradient-to-b from-mint-100 via-mint-50 to-slate-50">
        <div className="mx-auto grid max-w-7xl items-center gap-10 px-4 py-14 sm:px-6 lg:grid-cols-2 lg:py-20">
          <div>
            <span className="chip bg-white text-forest-800 shadow-card"><Sparkles size={12} />GHG Protocol · ISO 14064-1 aligned · India-first data</span>
            <h1 className="mt-4 text-4xl font-bold leading-tight tracking-tight text-slate-900 sm:text-5xl">
              Measure, understand and reduce your conference's carbon footprint
            </h1>
            <p className="mt-4 max-w-xl text-lg text-slate-600">
              Enter your event's travel, accommodation, energy, catering, waste and materials. Get a transparent, auditable footprint in
              tonnes CO₂e, see the biggest sources, test alternatives and download a professional report.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <button onClick={start} className="btn-primary px-6 py-3 text-base">Calculate My Conference Footprint <ArrowRight size={18} /></button>
              <Link to="/methodology" className="btn-secondary px-5 py-3 text-base">How it works</Link>
            </div>
            <p className="mt-4 text-sm text-slate-500">No sign-up needed. Progress is saved automatically.</p>
          </div>
          <div className="card p-6">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Every number is traceable</h2>
            <div className="mt-4 rounded-xl bg-slate-900 p-4 font-mono text-[13px] leading-relaxed text-slate-100">
              <div className="text-forest-300">emissions = activity data × emission factor</div>
              <div className="mt-3 text-slate-400"># venue electricity, Bengaluru</div>
              <div>1,800 kWh × 0.678 kg CO₂e/kWh</div>
              <div className="text-slate-400">  ↳ CEA CO₂ Baseline Database v22.0, FY 2025-26</div>
              <div className="mt-3 text-slate-400"># 10 speakers, Delhi ⇄ Bengaluru</div>
              <div>34,000 pkm × 0.126 kg CO₂e/pkm</div>
              <div className="text-slate-400">  ↳ DESNZ 2026 short-haul economy, incl. RF</div>
            </div>
            <ul className="mt-5 grid gap-3 text-sm text-slate-600 sm:grid-cols-2">
              <li className="flex gap-2"><Database size={16} className="mt-0.5 text-forest-700" />416 documented factors from downloaded official datasets</li>
              <li className="flex gap-2"><ShieldCheck size={16} className="mt-0.5 text-forest-700" />Missing data is flagged, never counted as zero</li>
              <li className="flex gap-2"><BarChart3 size={16} className="mt-0.5 text-forest-700" />Dashboard, what-if scenarios and recommendations</li>
              <li className="flex gap-2"><FileText size={16} className="mt-0.5 text-forest-700" />Reproducible PDF reports with factor versions</li>
            </ul>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-14 sm:px-6">
        <h2 className="text-2xl font-bold text-slate-900">Seven simple steps</h2>
        <p className="mt-1 text-slate-600">Only basic conference details are required - every other module is optional and clearly marked as not reported if skipped.</p>
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {modules.map(({ icon: I, t, d }) => (
            <div key={t} className="card p-5">
              <div className="mb-3 inline-flex rounded-xl bg-mint-100 p-2 text-forest-700"><I size={20} /></div>
              <h3 className="font-semibold text-slate-900">{t}</h3>
              <p className="mt-1 text-sm text-slate-600">{d}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 pb-16 sm:px-6">
        <div className="card p-6">
          <div className="flex items-center gap-2"><FlaskConical size={18} className="text-forest-700" /><h2 className="text-lg font-semibold">Explore a sample conference</h2></div>
          <p className="mt-1 text-sm text-slate-600">Illustrative, clearly labelled sample data - see the full dashboard and report in one click.</p>
          {err && <div className="mt-3"><Alert kind="error">{err}</Alert></div>}
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            {samples.map((s) => (
              <button key={s.id} onClick={() => openSample(s.id)} disabled={!!busy}
                className="rounded-xl border border-slate-200 p-4 text-left transition hover:border-forest-400 hover:bg-mint-50 disabled:opacity-60">
                <div className="font-medium text-slate-900">{s.title.replace(" (SAMPLE DATA)", "")}</div>
                <div className="mt-1 text-xs text-slate-500">{s.description}</div>
                <div className="mt-3 text-sm font-semibold text-forest-700">{busy === s.id ? "Calculating…" : "View results →"}</div>
              </button>
            ))}
            {samples.length === 0 && <p className="text-sm text-slate-500">Start the backend to load samples.</p>}
          </div>
        </div>
      </section>
    </div>
  );
}
