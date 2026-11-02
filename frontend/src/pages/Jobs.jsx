import { useEffect, useState } from "react";
import { api } from "../api.js";
import Filters from "../components/Filters.jsx";
import JobRow from "../components/JobRow.jsx";

const EMPTY = {
  q: "", role: "", country: "", location: "", workplace_type: "", remote_scope: "", experience: "",
  include_unspecified_experience: false, posted_within_days: "", skills: "", source: "",
  sort: "newest", verified_only: false, mnc_only: false,
};

export default function Jobs({ loggedIn }) {
  const [filters, setFilters] = useState(EMPTY);
  const [debounced, setDebounced] = useState(EMPTY);
  const [page, setPage] = useState(1);
  const [data, setData] = useState({ items: [], total: 0, page_size: 20 });
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => { api("/jobs/stats").then(setStats).catch(() => {}); }, []);

  useEffect(() => {
    const t = setTimeout(() => { setDebounced(filters); setPage(1); }, 350);
    return () => clearTimeout(t);
  }, [filters]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true); setError("");
    const params = { ...debounced, page, page_size: 20 };
    if (params.workplace_type !== "remote") params.remote_scope = "";
    if (!params.experience) params.include_unspecified_experience = false;
    api("/jobs", { params })
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [debounced, page]);

  const pages = Math.max(1, Math.ceil(data.total / (data.page_size || 20)));

  return (
    <div className="mx-auto grid max-w-7xl gap-6 px-4 py-6 lg:grid-cols-[17rem_1fr]">
      <aside className="h-fit rounded border border-line bg-white p-4 lg:sticky lg:top-4">
        <Filters value={filters} onChange={setFilters} onReset={() => setFilters(EMPTY)} sources={stats?.sources ?? []} />
      </aside>
      <main>
        {stats && (
          <p className="mb-4 text-sm text-ink/70">
            {stats.total_active.toLocaleString()} active jobs · {stats.last_24h} published in the last 24 h · {stats.last_7d} in 7 days ·{" "}
            {stats.verified} verified · {stats.remote} remote ({stats.remote_worldwide} worldwide)
            {stats.without_published_date > 0 && ` · ${stats.without_published_date} without a publication date`}
          </p>
        )}
        {error && <p role="alert" className="mb-3 rounded bg-red-50 p-3 text-sm text-red-800">Could not load jobs: {error}</p>}
        {!loading && !error && data.items.length === 0 && (
          <div className="rounded border border-line bg-white p-6 text-sm">
            <p className="font-semibold">No jobs match these filters.</p>
            <p className="mt-1 text-ink/70">
              {stats && stats.total_active === 0
                ? "The database is empty. Fetch jobs with: python -m app.cli ingest"
                : "Widen the date range or clear a filter."}
            </p>
          </div>
        )}
        <p className="mb-2 text-sm font-medium" aria-live="polite">{loading ? "Loading…" : `${data.total.toLocaleString()} jobs`}</p>
        <ul className="rounded border border-line">
          {data.items.map((j) => <JobRow key={j.id} job={j} loggedIn={loggedIn} />)}
        </ul>
        {pages > 1 && (
          <nav className="mt-4 flex items-center justify-between" aria-label="Pagination">
            <button className="btn-ghost" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
            <span className="text-sm">Page {page} of {pages}</span>
            <button className="btn-ghost" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</button>
          </nav>
        )}
      </main>
    </div>
  );
}
