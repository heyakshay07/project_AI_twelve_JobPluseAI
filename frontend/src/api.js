const KEY = "jobpulse.tokens";
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
const API_ROOT = `${API_BASE_URL}/api`;

export const tokens = {
  get: () => { try { return JSON.parse(localStorage.getItem(KEY)) || null; } catch { return null; } },
  set: (t) => localStorage.setItem(KEY, JSON.stringify(t)),
  clear: () => localStorage.removeItem(KEY),
};

async function refresh() {
  const t = tokens.get();
  if (!t?.refresh_token) return false;
  const r = await fetch(`${API_ROOT}/auth/refresh`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: t.refresh_token }),
  });
  if (!r.ok) { tokens.clear(); return false; }
  tokens.set(await r.json());
  return true;
}

export async function api(path, { method = "GET", body, params } = {}, retry = true) {
  const qs = params
    ? "?" + new URLSearchParams(Object.entries(params).filter(([, v]) => v !== "" && v != null && v !== false)).toString()
    : "";
  const headers = { "Content-Type": "application/json" };
  const t = tokens.get();
  if (t?.access_token) headers.Authorization = `Bearer ${t.access_token}`;
  const res = await fetch(`${API_ROOT}${path}${qs}`, { method, headers, body: body ? JSON.stringify(body) : undefined });
  if (res.status === 401 && retry && t && (await refresh())) return api(path, { method, body, params }, false);
  if (!res.ok) {
    let detail = res.statusText;
    try { const j = await res.json(); detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch {}
    throw new Error(detail);
  }
  return res.json();
}
