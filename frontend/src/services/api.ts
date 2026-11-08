import type { CalcResult, Calculation, ConferenceInput, Options, Scenario } from "../types";

const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") || "";
const TOKEN_KEY = "ccc_token";
const USER_KEY = "ccc_user";

export interface User { id: number; email: string | null; name: string | null; role: string }

function safeGet(k: string): string | null { try { return localStorage.getItem(k); } catch { return null; } }
function safeSet(k: string, v: string | null) { try { v === null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch { /* storage unavailable */ } }

export class ApiError extends Error {
  status: number; details: unknown;
  constructor(status: number, message: string, details?: unknown) { super(message); this.status = status; this.details = details; }
}

export function formatApiError(e: unknown): string {
  if (e instanceof ApiError) {
    if (Array.isArray(e.details)) {
      return (e.details as { loc?: (string | number)[]; msg: string }[])
        .map((d) => `${(d.loc || []).filter((x) => x !== "body").join(" › ")}: ${d.msg.replace(/^Value error, /, "")}`).join("\n");
    }
    return e.message;
  }
  return e instanceof Error ? e.message : String(e);
}

export function currentUser(): User | null { const u = safeGet(USER_KEY); return u ? JSON.parse(u) : null; }
export function logout() { safeSet(TOKEN_KEY, null); safeSet(USER_KEY, null); }

async function ensureToken(): Promise<string> {
  let t = safeGet(TOKEN_KEY);
  if (!t) {
    const r = await fetch(`${BASE}/api/auth/guest`, { method: "POST" });
    if (!r.ok) throw new ApiError(r.status, "Could not start a session - is the backend running?");
    const js = await r.json();
    t = js.token as string;
    safeSet(TOKEN_KEY, t);
    safeSet(USER_KEY, JSON.stringify(js.user));
  }
  return t!;
}

async function request<T>(path: string, opts: RequestInit = {}, auth = true, retry = true): Promise<T> {
  const headers: Record<string, string> = { ...(opts.headers as Record<string, string>) };
  if (opts.body && !(opts.body instanceof FormData)) headers["Content-Type"] = "application/json";
  if (auth) headers["Authorization"] = `Bearer ${await ensureToken()}`;
  let r: Response;
  try { r = await fetch(`${BASE}${path}`, { ...opts, headers }); }
  catch { throw new ApiError(0, "Cannot reach the server. Check that the backend is running."); }
  if (r.status === 401 && auth && retry) { logout(); return request<T>(path, opts, auth, false); }
  if (!r.ok) {
    let detail: unknown = r.statusText;
    try { detail = (await r.json()).detail; } catch { /* not json */ }
    throw new ApiError(r.status, typeof detail === "string" ? detail : "Please correct the highlighted inputs.", detail);
  }
  if (r.status === 204) return undefined as T;
  const ct = r.headers.get("content-type") || "";
  return (ct.includes("application/json") ? r.json() : r.blob()) as Promise<T>;
}

async function authCall(path: string, body: object) {
  const r = await request<{ token: string; user: User }>(path, { method: "POST", body: JSON.stringify(body) }, path === "/api/auth/upgrade");
  safeSet(TOKEN_KEY, r.token); safeSet(USER_KEY, JSON.stringify(r.user));
  return r.user;
}

export interface ConferenceSummary {
  id: number; name: string; country: string; state_city: string | null; start_date: string | null; end_date: string | null;
  days: number | null; format: string; conference_type: string; current_step: number; is_sample: boolean; updated_at: string;
  latest_calculation: { id: number; total_kg: number; created_at: string } | null;
}

export const api = {
  login: (email: string, password: string) => authCall("/api/auth/login", { email, password }),
  register: (email: string, password: string, name?: string) =>
    currentUser()?.role === "guest" ? authCall("/api/auth/upgrade", { email, password, name }) : authCall("/api/auth/register", { email, password, name }),
  me: () => request<User>("/api/auth/me"),
  options: () => request<Options>("/api/meta/options", {}, false),
  airports: (q: string) => request<{ iata: string; name: string; city: string; country: string }[]>(`/api/meta/airports?q=${encodeURIComponent(q)}`, {}, false),
  distance: (origin: string, destination: string, mode: string) =>
    request<{ distance_km?: number; source?: string; method?: string; error?: string; note?: string }>(
      `/api/meta/distance?origin=${encodeURIComponent(origin)}&destination=${encodeURIComponent(destination)}&mode=${mode}`, {}, false),
  preview: (input: ConferenceInput) => request<CalcResult>("/api/calculate", { method: "POST", body: JSON.stringify(input) }, false),
  validate: (input: ConferenceInput) => request<{ valid: boolean; errors: { loc: string[]; msg: string }[] }>("/api/validate", { method: "POST", body: JSON.stringify(input) }, false),
  listConferences: () => request<ConferenceSummary[]>("/api/conferences"),
  getConference: (id: number) => request<ConferenceSummary & { input: ConferenceInput }>(`/api/conferences/${id}`),
  createConference: (input: ConferenceInput, step: number) =>
    request<ConferenceSummary & { input: ConferenceInput }>("/api/conferences", { method: "POST", body: JSON.stringify({ input, current_step: step }) }),
  updateConference: (id: number, input: ConferenceInput, step: number) =>
    request<ConferenceSummary & { input: ConferenceInput }>(`/api/conferences/${id}`, { method: "PUT", body: JSON.stringify({ input, current_step: step }) }),
  deleteConference: (id: number) => request<void>(`/api/conferences/${id}`, { method: "DELETE" }),
  calculate: (id: number) => request<Calculation>(`/api/conferences/${id}/calculate`, { method: "POST" }),
  listCalculations: (id: number) => request<{ id: number; total_kg: number; created_at: string; factor_set_version: string }[]>(`/api/conferences/${id}/calculations`),
  getCalculation: (id: number) => request<Calculation>(`/api/calculations/${id}`),
  verify: (id: number) => request<{ reproducible: boolean; stored_total_kg: number; recomputed_with_pinned_factors_kg: number;
    recomputed_with_current_factors_kg: number; factors_changed_since: string[] }>(`/api/calculations/${id}/verify`),
  runScenario: (calcId: number, body: object) => request<Scenario>(`/api/calculations/${calcId}/scenarios`, { method: "POST", body: JSON.stringify(body) }),
  presets: () => request<{ preset: string; title: string; category: string; params: Record<string, unknown> }[]>("/api/scenario-presets", {}, false),
  generateReport: (calcId: number) => request<{ id: number; filename: string; sha256: string; size_bytes: number }>(`/api/calculations/${calcId}/report`, { method: "POST" }),
  downloadReport: async (reportId: number, filename: string) => {
    const blob = await request<Blob>(`/api/reports/${reportId}/download`);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = filename; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  },
  importTransport: (file: File, tripType: string) => {
    const fd = new FormData(); fd.append("file", file);
    return request<{ total_rows: number; valid_rows: number; invalid_rows: number; duplicates: number; entries: Record<string, unknown>[];
      errors: { row: number; message: string }[]; warnings: { row: number; message: string }[]; column_mapping: Record<string, string>;
      unrecognised_columns: string[] }>(`/api/imports/transport?trip_type=${tripType}`, { method: "POST", body: fd });
  },
  templateUrl: `${BASE}/api/imports/transport/template`,
  samples: () => request<{ id: string; title: string; description: string; participants: number }[]>("/api/samples", {}, false),
  loadSample: (id: string) => request<ConferenceSummary>(`/api/samples/${id}/load`, { method: "POST" }),
  factors: (params: { category?: string; q?: string; include_inactive?: boolean }) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== "").map(([k, v]) => [k, String(v)]));
    return request<Record<string, any>[]>(`/api/factors?${qs}`, {}, false);
  },
  sources: () => request<Record<string, any>[]>("/api/sources", {}, false),
  datasetVersions: () => request<{ factor_set_version: string; dataset_versions: Record<string, any> }>("/api/dataset-versions", {}, false),
  adminStats: () => request<Record<string, number>>("/api/admin/stats"),
  adminCalculations: () => request<Record<string, any>[]>("/api/admin/calculations"),
  adminAddFactor: (f: object) => request<Record<string, any>>("/api/admin/factors", { method: "POST", body: JSON.stringify(f) }),
  adminSetActive: (factorId: string, active: boolean) =>
    request<Record<string, any>>(`/api/admin/factors/${encodeURIComponent(factorId)}/${active ? "activate" : "deactivate"}`, { method: "POST" }),
};
