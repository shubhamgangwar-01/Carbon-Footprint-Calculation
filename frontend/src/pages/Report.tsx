import { CheckCircle2, FileDown, FileText, Loader2, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { Alert, Card, Spinner } from "../components/ui";
import { ResultsHeader, useCalculation } from "../dashboard/useCalculation";
import { api, formatApiError } from "../services/api";
import { fmt } from "../utils/format";

const CONTENTS = ["Conference information & reporting boundary", "Methodology (GHG Protocol / ISO 14064-1)", "Total, per-participant and per-day footprint",
  "Category breakdown with charts", "Activity-level calculation table", "Emission-factor sources and dataset versions", "Assumptions and exclusions",
  "Actual vs. estimated data, data quality and uncertainty", "Sustainability recommendations", "Scenario comparison", "Gross, market-based and offsets (separate)", "Reporting date & reproducibility statement"];

export default function Report() {
  const { calcId } = useParams();
  const id = Number(calcId);
  const { calc, error, reload } = useCalculation(id);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [verify, setVerify] = useState<Awaited<ReturnType<typeof api.verify>> | null>(null);
  if (error) return <div className="mx-auto max-w-3xl p-6"><Alert kind="error">{error}</Alert></div>;
  if (!calc) return <Spinner />;
  const generate = async () => {
    setBusy(true); setErr(null);
    try { const r = await api.generateReport(id); await api.downloadReport(r.id, r.filename); reload(); } catch (e) { setErr(formatApiError(e)); } finally { setBusy(false); }
  };
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <ResultsHeader calc={calc} />
      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Sustainability report (PDF)" icon={<FileText size={20} />} className="lg:col-span-2"
          subtitle={`Generated from this stored calculation only - its numbers always match the dashboard for calculation #${id}.`}>
          <div className="rounded-xl bg-mint-50 p-4">
            <div className="text-sm text-slate-600">Total footprint in this report</div>
            <div className="text-3xl font-bold text-forest-800">{fmt(calc.result.total_tonnes, 2)} t CO₂e</div>
            <div className="text-sm text-slate-500">{fmt(calc.result.per_participant_kg, 1)} kg CO₂e per participant · factor set {calc.result.factor_set_version}</div>
          </div>
          <h3 className="mt-5 text-sm font-semibold text-slate-700">Contents</h3>
          <ul className="mt-2 grid gap-1.5 text-sm text-slate-600 sm:grid-cols-2">{CONTENTS.map((c) => <li key={c} className="flex gap-2"><CheckCircle2 size={16} className="mt-0.5 shrink-0 text-forest-600" />{c}</li>)}</ul>
          {err && <div className="mt-4"><Alert kind="error">{err}</Alert></div>}
          <button className="btn-primary mt-6 px-6 py-3" onClick={generate} disabled={busy}>{busy ? <Loader2 size={18} className="animate-spin" /> : <FileDown size={18} />}Generate & download PDF</button>
        </Card>
        <div className="space-y-6">
          <Card title="Previously generated" subtitle="Stored with a SHA-256 checksum">
            {calc.reports.length === 0 ? <p className="text-sm text-slate-500">None yet.</p> : (
              <ul className="space-y-2 text-sm">{calc.reports.slice().reverse().map((r) => (
                <li key={r.id} className="flex items-center justify-between gap-2 rounded-lg border border-slate-200 p-2">
                  <div className="min-w-0"><div className="truncate font-medium">{new Date(r.created_at).toLocaleString()}</div><div className="truncate font-mono text-[10px] text-slate-400">{r.sha256}</div></div>
                  <button className="btn-ghost px-2" onClick={() => api.downloadReport(r.id, r.filename)} aria-label="Download"><FileDown size={16} /></button>
                </li>))}</ul>
            )}
          </Card>
          <Card title="Reproducibility check" icon={<ShieldCheck size={20} />} subtitle="Recompute from the stored inputs with the exact factor versions used.">
            <button className="btn-secondary" onClick={() => api.verify(id).then(setVerify).catch((e) => setErr(formatApiError(e)))}>Verify</button>
            {verify && (
              <div className="mt-3 space-y-2 text-sm">
                <Alert kind={verify.reproducible ? "success" : "error"}>{verify.reproducible ? "Reproducible: identical total with pinned factors." : "Not reproducible - a pinned factor is missing."}</Alert>
                <p className="text-slate-600">Stored: {fmt(verify.stored_total_kg, 1)} kg · with current factors: {fmt(verify.recomputed_with_current_factors_kg, 1)} kg</p>
                {verify.factors_changed_since.length > 0 && <p className="text-xs text-amber-700">Factors updated since: {verify.factors_changed_since.join(", ")}. Recalculate to use them; this stored result is unchanged.</p>}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
