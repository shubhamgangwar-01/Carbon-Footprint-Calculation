import { AlertCircle, AlertTriangle, CheckCircle2, Info, Loader2 } from "lucide-react";
import { useId, useState, type ReactNode } from "react";
import { DQ_STYLE, DT_STYLE, STATUS_STYLE } from "../utils/format";

export function Tooltip({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <span className="relative inline-flex">
      <button type="button" aria-describedby={id} aria-label="More information" onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)} onFocus={() => setOpen(true)} onBlur={() => setOpen(false)}
        className="text-slate-400 hover:text-forest-700 focus:text-forest-700 focus:outline-none">
        <Info size={14} />
      </button>
      {open && (
        <span id={id} role="tooltip" className="absolute bottom-full left-1/2 z-30 mb-2 w-64 -translate-x-1/2 rounded-lg bg-slate-900 px-3 py-2 text-xs font-normal leading-relaxed text-white shadow-lg">
          {text}
        </span>
      )}
    </span>
  );
}

interface FieldProps { label: string; tip?: string; unit?: string; error?: string; optional?: boolean; children: ReactNode; className?: string }
export function Field({ label, tip, unit, error, optional, children, className = "" }: FieldProps) {
  return (
    <div className={className}>
      <label className="label">
        <span>{label}</span>
        {unit && <span className="font-normal text-slate-400">({unit})</span>}
        {optional && <span className="ml-1 text-xs font-normal text-slate-400">optional</span>}
        {tip && <Tooltip text={tip} />}
      </label>
      {children}
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  );
}

export function NumberInput({ value, onChange, min = 0, step = "any", placeholder, error, ariaLabel }:
  { value: number | null | undefined; onChange: (v: number | null) => void; min?: number; step?: string; placeholder?: string; error?: boolean; ariaLabel?: string }) {
  return (
    <input type="number" inputMode="decimal" min={min} step={step} aria-label={ariaLabel} placeholder={placeholder}
      className={`input ${error ? "input-error" : ""}`} value={value ?? ""}
      onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))} />
  );
}

export function Select({ value, onChange, options, ariaLabel }:
  { value: string | null | undefined; onChange: (v: string) => void; options: { value: string; label: string }[]; ariaLabel?: string }) {
  return (
    <select aria-label={ariaLabel} className="input" value={value ?? ""} onChange={(e) => onChange(e.target.value)}>
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}

export function Toggle({ checked, onChange, label, tip }: { checked: boolean; onChange: (v: boolean) => void; label: string; tip?: string }) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-slate-700">
      <input type="checkbox" className="h-4 w-4 rounded border-slate-300 text-forest-700 focus:ring-forest-500" checked={checked}
        onChange={(e) => onChange(e.target.checked)} />
      {label}{tip && <Tooltip text={tip} />}
    </label>
  );
}

export function Card({ title, subtitle, icon, actions, children, className = "" }:
  { title?: ReactNode; subtitle?: ReactNode; icon?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card p-5 sm:p-6 ${className}`}>
      {(title || actions) && (
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            {icon && <div className="rounded-xl bg-mint-100 p-2 text-forest-700">{icon}</div>}
            <div>
              {title && <h2 className="text-base font-semibold text-slate-900">{title}</h2>}
              {subtitle && <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>}
            </div>
          </div>
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

export function Alert({ kind = "info", children }: { kind?: "info" | "warning" | "error" | "success"; children: ReactNode }) {
  const s = {
    info: ["bg-sky-50 border-sky-200 text-sky-900", <Info key="i" size={16} />],
    warning: ["bg-amber-50 border-amber-200 text-amber-900", <AlertTriangle key="w" size={16} />],
    error: ["bg-red-50 border-red-200 text-red-800", <AlertCircle key="e" size={16} />],
    success: ["bg-forest-50 border-forest-200 text-forest-900", <CheckCircle2 key="s" size={16} />],
  }[kind];
  return <div role={kind === "error" ? "alert" : "status"} className={`flex gap-2 rounded-xl border px-3 py-2.5 text-sm ${s[0]}`}><span className="mt-0.5 shrink-0">{s[1]}</span><div className="min-w-0 whitespace-pre-line">{children}</div></div>;
}

export const Spinner = ({ label = "Loading…" }: { label?: string }) => (
  <div className="flex items-center justify-center gap-2 py-10 text-sm text-slate-500" role="status"><Loader2 className="animate-spin" size={18} />{label}</div>
);

export const StatusChip = ({ status }: { status: string }) => <span className={`chip ${STATUS_STYLE[status] || "bg-slate-100"}`}>{status.replace(/_/g, " ")}</span>;
export const DQChip = ({ q }: { q: string }) => <span className={`chip ${DQ_STYLE[q] || "bg-slate-100"}`}>{q}</span>;
export const DTChip = ({ t }: { t: string }) => <span className={`chip ${DT_STYLE[t] || "bg-slate-100"}`}>{t}</span>;

export function DataTypeSelect({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <Select ariaLabel="Data type" value={value} onChange={onChange} options={[
      { value: "actual", label: "Actual (measured / records)" },
      { value: "estimated", label: "Estimated" },
      { value: "default", label: "Default / assumed" },
    ]} />
  );
}

export function NotApplicable({ checked, onChange, what }: { checked: boolean; onChange: (v: boolean) => void; what: string }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-3">
      <Toggle checked={checked} onChange={onChange} label={`${what} does not apply to this conference`}
        tip="Declaring a category 'not applicable' reports it as zero with that declaration recorded. Leaving it empty reports it as 'not reported' - never silently as zero." />
    </div>
  );
}
