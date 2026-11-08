import { ArrowLeft, ArrowRight, Calculator, Check, CloudOff, Loader2, Save } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Alert } from "../components/ui";
import AccommodationForm from "../forms/AccommodationForm";
import BasicInfoForm, { validateBasic } from "../forms/BasicInfoForm";
import EnergyForm from "../forms/EnergyForm";
import FoodForm from "../forms/FoodForm";
import MaterialsForm from "../forms/MaterialsForm";
import ReviewStep from "../forms/ReviewStep";
import TransportForm from "../forms/TransportForm";
import WasteForm from "../forms/WasteForm";
import { api, formatApiError } from "../services/api";
import { STEPS, useConference } from "../state/ConferenceContext";

const FORMS: Record<string, () => JSX.Element> = {
  basic: BasicInfoForm, transport: TransportForm, accommodation: AccommodationForm, energy: EnergyForm,
  food: FoodForm, waste: WasteForm, materials: MaterialsForm, review: ReviewStep,
};

export default function Wizard() {
  const { step = "basic" } = useParams();
  const nav = useNavigate();
  const { input, save, saving, saveError, lastSaved, conferenceId } = useConference();
  const idx = Math.max(0, STEPS.findIndex((s) => s.key === step));
  const [localErr, setLocalErr] = useState<string | null>(null);
  const [calculating, setCalculating] = useState(false);
  const Form = FORMS[STEPS[idx].key];
  useEffect(() => { window.scrollTo({ top: 0 }); setLocalErr(null); }, [idx]);

  const go = async (to: number) => {
    setLocalErr(null);
    if (to > idx || STEPS[idx].key === "basic") {
      const err = validateBasic(input);
      if (err) { setLocalErr(err); if (STEPS[idx].key !== "basic") nav("/calculator/basic"); return; }
    }
    const id = await save(Math.max(to, idx));
    if (id === null) return; // server validation errors are shown
    nav(`/calculator/${STEPS[to].key}`);
  };

  const calculate = async () => {
    const err = validateBasic(input);
    if (err) { setLocalErr(err); return; }
    setCalculating(true); setLocalErr(null);
    try {
      const id = await save(STEPS.length - 1);
      if (id === null) return;
      const calc = await api.calculate(id);
      nav(`/results/${calc.id}`);
    } catch (e) { setLocalErr(formatApiError(e)); } finally { setCalculating(false); }
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
      {/* progress indicator */}
      <nav aria-label="Progress" className="mb-6">
        <div className="mb-2 flex items-center justify-between text-sm">
          <span className="font-medium text-slate-700">Step {idx + 1} of {STEPS.length}: {STEPS[idx].label}</span>
          <span className="flex items-center gap-1 text-xs text-slate-500">
            {saving ? <><Loader2 size={12} className="animate-spin" />Saving…</> : saveError ? <><CloudOff size={12} />Not saved</> :
              lastSaved || conferenceId ? <><Check size={12} className="text-forest-600" />Saved{lastSaved ? ` ${lastSaved.toLocaleTimeString()}` : ""}</> : "Draft stored on this device"}
          </span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-slate-200">
          <div className="h-full rounded-full bg-forest-600 transition-all" style={{ width: `${((idx + 1) / STEPS.length) * 100}%` }} />
        </div>
        <ol className="mt-3 hidden grid-cols-8 gap-1 md:grid">
          {STEPS.map((s, i) => (
            <li key={s.key}>
              <button onClick={() => go(i)} disabled={!conferenceId && i > 0}
                className={`w-full rounded-lg px-1 py-1.5 text-xs font-medium transition ${i === idx ? "bg-forest-700 text-white" : i < idx ? "bg-mint-100 text-forest-800 hover:bg-forest-100" : "text-slate-500 hover:bg-slate-100 disabled:hover:bg-transparent"}`}>
                {s.label}
              </button>
            </li>
          ))}
        </ol>
      </nav>

      <Form />

      {(localErr || saveError) && <div className="mt-4"><Alert kind="error">{localErr || saveError}</Alert></div>}

      <div className="sticky bottom-0 z-20 mt-6 flex items-center justify-between gap-3 border-t border-slate-200 bg-slate-50/95 py-4 backdrop-blur">
        <button className="btn-secondary" onClick={() => go(idx - 1)} disabled={idx === 0 || saving}><ArrowLeft size={16} />Back</button>
        <div className="flex gap-2">
          {idx > 0 && idx < STEPS.length - 1 && (
            <button className="btn-ghost hidden sm:inline-flex" onClick={() => save(idx)} disabled={saving}><Save size={16} />Save progress</button>
          )}
          {idx < STEPS.length - 1 ? (
            <button className="btn-primary" onClick={() => go(idx + 1)} disabled={saving}>Next<ArrowRight size={16} /></button>
          ) : (
            <button className="btn-primary" onClick={calculate} disabled={calculating || saving}>
              {calculating ? <Loader2 size={16} className="animate-spin" /> : <Calculator size={16} />}Calculate footprint
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
