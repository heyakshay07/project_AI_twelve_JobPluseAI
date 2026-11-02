import { useState } from "react";
import { api } from "../api.js";

const STATUS = {
  verified_official: { label: "Verified: official company site", cls: "bg-emerald-100 text-emerald-900" },
  verified_trusted_ats: { label: "Verified: trusted ATS", cls: "bg-emerald-100 text-emerald-900" },
  partially_verified: { label: "Partially verified", cls: "bg-amber-100 text-amber-900" },
  unverified: { label: "Unverified", cls: "bg-slate-200 text-slate-800" },
  expired: { label: "Expired", cls: "bg-slate-300 text-slate-700" },
  closed: { label: "Closed", cls: "bg-slate-300 text-slate-700" },
  suspicious: { label: "Suspicious", cls: "bg-red-100 text-red-900" },
};

function experienceLabel(j) {
  if (j.experience_status === "fresher") return "Fresher";
  if (j.experience_status === "not_specified" || j.minimum_experience == null) return "Experience not specified";
  if (j.maximum_experience == null) return `${j.minimum_experience}+ years`;
  return `${j.minimum_experience}–${j.maximum_experience} years`;
}

function workplaceLabel(j) {
  if (j.workplace_type === "remote") {
    const scope = { worldwide: "worldwide", country_restricted: "restricted to a country", unknown: "scope not stated" }[j.remote_scope] || "scope not stated";
    return `Remote (${scope})`;
  }
  return { hybrid: "Hybrid", onsite: "Onsite" }[j.workplace_type] || "Workplace not stated";
}

function ago(iso) {
  if (!iso) return null;
  const hours = (Date.now() - new Date(iso).getTime()) / 36e5;
  if (hours < 1) return "under an hour ago";
  if (hours < 24) return `${Math.floor(hours)} hours ago`;
  const days = Math.floor(hours / 24);
  return days === 1 ? "1 day ago" : `${days} days ago`;
}

const fmt = (iso) => (iso ? new Date(iso).toLocaleString() : "never");

export default function JobRow({ job: initial, loggedIn }) {
  const [job, setJob] = useState(initial);
  const [detail, setDetail] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const st = STATUS[job.verification_status] || STATUS.unverified;

  async function toggleDetail() {
    if (detail) return setDetail(null);
    try { setDetail(await api(`/jobs/${job.id}`)); } catch (e) { setError(e.message); }
  }

  async function check() {
    setBusy(true); setError("");
    try {
      const d = await api(`/jobs/${job.id}/verify`, { method: "POST" });
      setJob({ ...job, ...d }); if (detail) setDetail(d);
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }

  const posted = ago(job.first_published_at);
  return (
    <li className="border-b border-line bg-white px-4 py-4 first:rounded-t last:rounded-b last:border-b-0">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h3 className="text-base font-semibold leading-snug">{job.title}</h3>
          <p className="mt-0.5 text-sm">
            <span className="font-medium">{job.company_name}</span>
            {job.company_is_mnc && <span className="ml-2 rounded bg-accent/10 px-1.5 py-0.5 text-xs font-medium text-accent">MNC</span>}
            <span className="text-ink/60"> · {job.location || "Location not stated"}{job.country && !job.location.includes(job.country) ? `, ${job.country}` : ""}</span>
          </p>
          <p className="mt-1 text-sm text-ink/80">
            {workplaceLabel(job)} · {experienceLabel(job)}
            {job.employment_type ? ` · ${job.employment_type}` : ""}
            {job.salary_min ? ` · ${Math.round(job.salary_min).toLocaleString()}${job.salary_max ? "–" + Math.round(job.salary_max).toLocaleString() : "+"} ${job.currency || ""}` : ""}
          </p>
          {job.skills.length > 0 && (
            <ul className="mt-2 flex flex-wrap gap-1.5">
              {job.skills.slice(0, 8).map((s) => <li key={s} className="rounded border border-line px-1.5 py-0.5 text-xs">{s}</li>)}
            </ul>
          )}
          <p className="mt-2 text-xs text-ink/60">
            {posted ? `Published ${posted}` : "Publication date not provided by source"} · fetched {fmt(job.fetched_at)} ·
            source: {job.source_name}{job.other_sources.length ? ` (also ${job.other_sources.join(", ")})` : ""}
          </p>
        </div>
        <div className="flex shrink-0 flex-col gap-2 sm:items-end">
          <span className={`rounded px-2 py-1 text-xs font-semibold ${st.cls}`} title={`Score ${job.verification_score}/100 · last checked ${fmt(job.last_verified_at)}`}>{st.label}</span>
          <a className="btn-primary text-center" href={job.application_url} target="_blank" rel="noopener noreferrer">Apply at source</a>
          <div className="flex gap-2">
            <button className="btn-ghost" onClick={toggleDetail}>{detail ? "Hide details" : "Details"}</button>
            {loggedIn && <button className="btn-ghost" disabled={busy} onClick={check}>{busy ? "Checking…" : "Check link"}</button>}
          </div>
        </div>
      </div>
      {error && <p role="alert" className="mt-2 text-sm text-red-700">{error}</p>}
      {detail && (
        <div className="mt-3 grid gap-4 border-t border-line pt-3 text-sm md:grid-cols-2">
          <div>
            <h4 className="mb-1 font-semibold">Description</h4>
            <p className="max-h-64 overflow-auto whitespace-pre-line text-ink/80">{detail.description || "No description provided."}</p>
          </div>
          <div>
            <h4 className="mb-1 font-semibold">Verification evidence</h4>
            {detail.verification_logs.length === 0 && <p className="text-ink/70">No checks yet. Log in and choose “Check link” to run them.</p>}
            <ul className="space-y-2">
              {detail.verification_logs.map((l, i) => (
                <li key={i} className="rounded border border-line p-2">
                  <p className="font-medium">{l.stage.replace("_", " ")}: {l.result.replace("_", " ")} <span className="font-normal text-ink/60">({fmt(l.created_at)})</span></p>
                  <pre className="mt-1 overflow-auto whitespace-pre-wrap text-xs text-ink/70">{JSON.stringify(l.evidence, null, 1)}</pre>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </li>
  );
}
