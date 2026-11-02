const COUNTRIES = ["India", "United States", "United Kingdom", "Canada", "Germany", "France", "Netherlands",
  "Australia", "Singapore", "United Arab Emirates", "Japan", "Ireland"];
const EXPERIENCE = [["fresher", "Fresher (0)"], ["0-1", "0–1 years"], ["1-2", "1–2 years"], ["2-4", "2–4 years"],
  ["4-6", "4–6 years"], ["6-8", "6–8 years"], ["8-10", "8–10 years"], ["10+", "10+ years"]];
const POSTED = [["1", "Last 24 hours"], ["3", "Last 3 days"], ["7", "Last 7 days"], ["14", "Last 14 days"], ["30", "Last 30 days"]];
const ROLES = [["frontend", "Frontend"], ["backend", "Backend"], ["software_developer", "Software Developer"],
  ["software_engineer", "Software Engineer"], ["ai_engineer", "AI Engineer"], ["gen_ai", "GenAI / Generative AI"],
  ["agentic_ai", "Agentic AI"]];

function Label({ text, children }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-semibold text-ink/70">{text}</span>
      {children}
    </label>
  );
}

export default function Filters({ value, onChange, onReset, sources = [] }) {
  const set = (k) => (e) => onChange({ ...value, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  return (
    <form className="space-y-3.5" onSubmit={(e) => e.preventDefault()} aria-label="Job filters">
      <Label text="Title or company">
        <input className="field" value={value.q} onChange={set("q")} placeholder="e.g. python, Stripe" />
      </Label>
      <Label text="Job role">
        <select className="field" value={value.role} onChange={set("role")}>
          <option value="">All IT roles</option>
          {ROLES.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
        </select>
      </Label>
      <Label text="Country">
        <select className="field" value={value.country} onChange={set("country")}>
          <option value="">Any country</option>
          {COUNTRIES.map((c) => <option key={c}>{c}</option>)}
        </select>
      </Label>
      <Label text="City or location text">
        <input className="field" value={value.location} onChange={set("location")} placeholder="e.g. Pune" />
      </Label>
      <Label text="Workplace">
        <select className="field" value={value.workplace_type} onChange={set("workplace_type")}>
          <option value="">Any</option>
          <option value="remote">Remote</option>
          <option value="hybrid">Hybrid</option>
          <option value="onsite">Onsite</option>
          <option value="unknown">Not stated</option>
        </select>
      </Label>
      {value.workplace_type === "remote" && (
        <Label text="Remote scope">
          <select className="field" value={value.remote_scope} onChange={set("remote_scope")}>
            <option value="">Any remote</option>
            <option value="worldwide">Worldwide</option>
            <option value="country_restricted">Restricted to a country</option>
            <option value="unknown">Scope not stated</option>
          </select>
        </Label>
      )}
      <Label text="Experience required">
        <select className="field" value={value.experience} onChange={set("experience")}>
          <option value="">Any</option>
          {EXPERIENCE.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </Label>
      {value.experience && (
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={value.include_unspecified_experience} onChange={set("include_unspecified_experience")} />
          Also show jobs that don’t state experience
        </label>
      )}
      <Label text="Posted">
        <select className="field" value={value.posted_within_days} onChange={set("posted_within_days")}>
          <option value="">Any time</option>
          {POSTED.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </Label>
      <Label text="Skills (all must match)">
        <input className="field" value={value.skills} onChange={set("skills")} placeholder="python, fastapi, rag" />
      </Label>
      <Label text="Source">
        <select className="field" value={value.source} onChange={set("source")}>
          <option value="">All sources</option>
          {sources.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </Label>
      <Label text="Sort by">
        <select className="field" value={value.sort} onChange={set("sort")}>
          <option value="newest">Newest published</option>
          <option value="fetched">Recently fetched</option>
          <option value="verification">Verification strength</option>
        </select>
      </Label>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={value.verified_only} onChange={set("verified_only")} /> Verified only
      </label>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={value.mnc_only} onChange={set("mnc_only")} /> MNC only
      </label>
      <button type="button" className="btn-ghost w-full" onClick={onReset}>Clear filters</button>
    </form>
  );
}
