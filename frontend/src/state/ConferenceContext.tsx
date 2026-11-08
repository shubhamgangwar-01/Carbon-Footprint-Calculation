import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { api, formatApiError } from "../services/api";
import type { ConferenceInput, Options } from "../types";

export const STEPS = [
  { key: "basic", label: "Conference" },
  { key: "transport", label: "Transport" },
  { key: "accommodation", label: "Accommodation" },
  { key: "energy", label: "Venue & energy" },
  { key: "food", label: "Food" },
  { key: "waste", label: "Waste" },
  { key: "materials", label: "Materials" },
  { key: "review", label: "Review" },
] as const;

export const emptyInput = (): ConferenceInput => ({
  basic: { name: "", country: "India", country_code: "IN", state_city: "", venue_name: "", venue_area_m2: null,
    start_date: null, end_date: null, days: null, attendees: 0, speakers: 0, organisers_staff: 0, volunteers: 0,
    virtual_attendees: 0, conference_type: "academic", format: "offline" },
  settings: { include_radiative_forcing: true, grid_reporting_year: null, reusable_item_uses_default: 5 },
  transport: [], transport_not_applicable: false, accommodation: [], accommodation_not_applicable: false,
  energy: null, food: null, waste: null, materials: null, offsets: { tonnes_co2e: 0, standard: null, retirement_reference: null },
});

const DRAFT_KEY = "ccc_draft";

interface Ctx {
  input: ConferenceInput;
  setInput: (fn: (prev: ConferenceInput) => ConferenceInput) => void;
  conferenceId: number | null;
  options: Options | null;
  saving: boolean;
  saveError: string | null;
  lastSaved: Date | null;
  save: (step: number) => Promise<number | null>;
  load: (id: number) => Promise<void>;
  reset: () => void;
}
const C = createContext<Ctx | null>(null);

export function ConferenceProvider({ children }: { children: ReactNode }) {
  const [input, setInputState] = useState<ConferenceInput>(() => {
    try { const d = localStorage.getItem(DRAFT_KEY); if (d) return { ...emptyInput(), ...JSON.parse(d).input }; } catch { /* ignore */ }
    return emptyInput();
  });
  const [conferenceId, setConferenceId] = useState<number | null>(() => {
    try { const d = localStorage.getItem(DRAFT_KEY); return d ? JSON.parse(d).id ?? null : null; } catch { return null; }
  });
  const [options, setOptions] = useState<Options | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [lastSaved, setLastSaved] = useState<Date | null>(null);
  const idRef = useRef(conferenceId);
  idRef.current = conferenceId;

  useEffect(() => { api.options().then(setOptions).catch(() => setOptions(null)); }, []);
  // local autosave (survives refresh even before the server copy exists)
  useEffect(() => {
    try { localStorage.setItem(DRAFT_KEY, JSON.stringify({ id: conferenceId, input })); } catch { /* storage unavailable */ }
  }, [input, conferenceId]);

  const setInput = useCallback((fn: (p: ConferenceInput) => ConferenceInput) => setInputState((p) => fn(p)), []);

  const save = useCallback(async (step: number) => {
    setSaving(true); setSaveError(null);
    try {
      const res = idRef.current ? await api.updateConference(idRef.current, input, step) : await api.createConference(input, step);
      setConferenceId(res.id); setLastSaved(new Date());
      return res.id;
    } catch (e) {
      setSaveError(formatApiError(e));
      return null;
    } finally { setSaving(false); }
  }, [input]);

  const load = useCallback(async (id: number) => {
    const c = await api.getConference(id);
    setInputState({ ...emptyInput(), ...c.input });
    setConferenceId(id);
  }, []);

  const reset = useCallback(() => { setInputState(emptyInput()); setConferenceId(null); setSaveError(null); setLastSaved(null); }, []);

  return <C.Provider value={{ input, setInput, conferenceId, options, saving, saveError, lastSaved, save, load, reset }}>{children}</C.Provider>;
}

export function useConference() {
  const c = useContext(C);
  if (!c) throw new Error("useConference outside provider");
  return c;
}
