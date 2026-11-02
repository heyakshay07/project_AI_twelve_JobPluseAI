import { useState } from "react";
import { api, tokens } from "../api.js";

export default function Auth({ onDone }) {
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ email: "", password: "", full_name: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const body = mode === "login" ? { email: form.email, password: form.password } : form;
      tokens.set(await api(`/auth/${mode === "login" ? "login" : "register"}`, { method: "POST", body }));
      onDone();
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  return (
    <div className="mx-auto max-w-sm px-4 py-12">
      <h1 className="mb-4 text-xl font-semibold">{mode === "login" ? "Log in" : "Create your account"}</h1>
      <form onSubmit={submit} className="space-y-3 rounded border border-line bg-white p-5">
        {mode === "register" && (
          <label className="block text-sm font-medium">Full name
            <input className="field mt-1" value={form.full_name} onChange={set("full_name")} autoComplete="name" />
          </label>
        )}
        <label className="block text-sm font-medium">Email
          <input className="field mt-1" type="email" required value={form.email} onChange={set("email")} autoComplete="email" />
        </label>
        <label className="block text-sm font-medium">Password
          <input className="field mt-1" type="password" required minLength={8} maxLength={64} value={form.password}
                 onChange={set("password")} autoComplete={mode === "login" ? "current-password" : "new-password"} />
        </label>
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
        <button className="btn-primary w-full" disabled={busy}>{busy ? "Please wait…" : mode === "login" ? "Log in" : "Create account"}</button>
      </form>
      <button className="mt-3 text-sm text-accent underline" onClick={() => setMode(mode === "login" ? "register" : "login")}>
        {mode === "login" ? "Need an account? Register" : "Already registered? Log in"}
      </button>
    </div>
  );
}
