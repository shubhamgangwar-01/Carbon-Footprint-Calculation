import { LogIn } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Alert, Card, Field } from "../components/ui";
import { api, currentUser, formatApiError } from "../services/api";

export default function Login() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const nav = useNavigate();
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setErr(null); setBusy(true);
    try {
      const u = mode === "login" ? await api.login(email, password) : await api.register(email, password, name);
      nav(u.role === "admin" ? "/admin" : "/conferences"); window.location.reload();
    } catch (x) { setErr(formatApiError(x)); } finally { setBusy(false); }
  };
  const guest = currentUser()?.role === "guest";
  return (
    <div className="mx-auto max-w-md px-4 py-12">
      <Card title={mode === "login" ? "Sign in" : "Create an account"} icon={<LogIn size={20} />}
        subtitle={mode === "register" && guest ? "Your current guest conferences will be kept." : "Accounts keep your conferences across devices. Admins manage emission factors."}>
        <form onSubmit={submit} className="space-y-4">
          {mode === "register" && <Field label="Name" optional><input className="input" value={name} onChange={(e) => setName(e.target.value)} /></Field>}
          <Field label="Email"><input type="email" required className="input" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" /></Field>
          <Field label="Password" tip="At least 8 characters."><input type="password" required minLength={8} className="input" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={mode === "login" ? "current-password" : "new-password"} /></Field>
          {err && <Alert kind="error">{err}</Alert>}
          <button className="btn-primary w-full" disabled={busy}>{mode === "login" ? "Sign in" : "Create account"}</button>
        </form>
        <button className="mt-4 text-sm text-forest-700 hover:underline" onClick={() => setMode(mode === "login" ? "register" : "login")}>
          {mode === "login" ? "No account? Create one" : "Already registered? Sign in"}
        </button>
      </Card>
    </div>
  );
}
