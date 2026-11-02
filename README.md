# JobPulse AI

Global IT job discovery, **verification** and (soon) resume-matching platform.
It aggregates jobs from several sources, normalises them, extracts experience and skills,
removes duplicates, and checks whether each application link is real — showing the evidence
instead of just a label.

**Current status: Phase 1 + first part of Phase 2/3/4** (foundation, real sources, filters, basic verification).

| Phase | Scope | Status |
|---|---|---|
| 1 | Project setup, PostgreSQL, JWT auth, FastAPI, React UI | Done |
| 2 | Adzuna, Remotive, Arbeitnow, Greenhouse, Lever | Done (see "Verified vs. not verified" below) |
| 3 | Normalisation, de-duplication, experience filters | Done. Celery/Redis scheduling is next |
| 4 | Company directory + verification engine | Basic version done (link, domain, fraud checks) |
| 5 | Resume upload, parsing, AI matching (pgvector + Groq) | Next |
| 6 | LangGraph agents, Instagram discovery | Planned |
| 7 | Application tracker, alerts, recommendations | Planned |
| 8 | Admin UI, rate limiting, hardening, deployment | Planned |

---

## 1. What is in this phase

- **Sources (modular, one file each in `backend/app/sources/`)**
  - `remotive` — remote software/data jobs, no key. Detects *worldwide* vs *country-restricted* remote.
  - `arbeitnow` — mostly Germany/EU, no key, filtered to IT roles.
  - `adzuna` — India, UK, USA… needs a free App ID + App Key. Skipped (and logged) if keys are missing.
  - `greenhouse` and `lever` — official company boards, no key. Companies come from the directory table.
- **Normalisation** — HTML stripping, skills extraction, country guess, workplace type, experience range.
- **Experience extraction** — `2–4 years` → min 2 / max 4, `3+` → min 3, `Freshers welcome` → fresher.
  If nothing is found the job is stored as **not specified**; experience is never guessed.
- **De-duplication** — same company + normalised title + location = one job; every source link is kept
  (`job_sources` table). If the company's own ATS reports the same job, its URL replaces the aggregator URL.
- **Verification engine** (`POST /api/jobs/{id}/verify`) — company-in-directory check, application-link check
  (status code, redirects, "no longer available" text), domain check, fraud signals (upfront fees,
  personal e-mail addresses, WhatsApp/Telegram hiring, gift-card payments). Every verdict stores its evidence
  in `job_verification_logs`. A plain HTTP 200 only ever gives **Partially verified**.
- **Auth** — register / login / refresh (JWT access + refresh tokens, bcrypt hashing), admin role.
- **React UI** — filter sidebar (title, role category, country, city, workplace, remote scope, experience, date posted,
  skills, source, verified-only, MNC-only, sort), job list with original links, evidence viewer, login.
- **Alembic migration**, **Docker Compose**, **40 automated tests**.

### Verification statuses

| Status | Meaning |
|---|---|
| `verified_official` | Link works and lands on the company's own domain (from the directory) |
| `verified_trusted_ats` | Job came from the company's own Greenhouse/Lever board, or the link works on a known ATS domain |
| `partially_verified` | Link works, but the site is not a known official/ATS domain |
| `unverified` | Not checked yet, or the link could not be reached |
| `expired` | 404/410 or "no longer available" text — job is hidden from search |
| `suspicious` | Fraud signals found (e.g. asks for a registration fee) |

### Verified vs. not verified (please read)

- The sandbox used to write this code had **no outbound access to the job APIs**, so the live endpoints were
  *not* called here. The parsers follow each provider's documented response format and are tested with
  mock responses of that shape. **Run the ingest command in step 4 on your machine and check
  `GET /api/admin/fetch-logs`; if a provider changed its format, the log shows exactly which source failed.**
- The Greenhouse/Lever company identifiers in `backend/data/companies.seed.json` are best-effort.
  A wrong identifier simply produces a logged 404 for that company — edit the seed file or add companies
  through the API. The directory status is `seeded`, not `verified`, until you confirm a domain.
- Adzuna links are Adzuna redirect URLs; Remotive links point to the Remotive page. Both start as
  **unverified** and become better-verified only through the link check.
  Remotive asks API users to credit them and to fetch only a few times per day.
- **Not integrated (by design):** LinkedIn, Indeed, Naukri, Glassdoor (no open public job-search API —
  use licensed feeds/partnerships) and Instagram (needs Meta app review; planned for Phase 6).
- **Role categories:** Frontend, Backend, Software Developer, Software Engineer, AI Engineer,
  GenAI / Generative AI, and Agentic AI are available in the job-role filter. These filter jobs returned
  by configured sources; availability depends on those sources and their company boards.

---

## 2. Project structure

```
jobpulse-ai/
├── README.md
├── .env.example
├── docker-compose.yml
├── backend/
│   ├── Dockerfile, requirements.txt, alembic.ini, pytest.ini
│   ├── migrations/versions/0001_initial_schema.py
│   ├── data/companies.seed.json          # company directory seed (ATS ids, career URLs)
│   ├── app/
│   │   ├── main.py, config.py, database.py, models.py, schemas.py, security.py, deps.py, cli.py
│   │   ├── routers/    auth.py  jobs.py  companies.py  admin.py
│   │   ├── services/   ingest.py  verification.py  experience.py  skills.py  location.py  text.py
│   │   └── sources/    base.py  remotive.py  arbeitnow.py  adzuna.py  greenhouse.py  lever.py
│   └── tests/
└── frontend/
    ├── Dockerfile, package.json, vite.config.js, tailwind.config.js
    └── src/  App.jsx  api.js  pages/{Jobs,Auth}.jsx  components/{Filters,JobRow}.jsx
```

---

## 3. Install and run

### Option A — Docker (easiest; includes PostgreSQL)

Prerequisite: Docker Desktop (or Docker Engine + Compose v2).

```bash
cd jobpulse-ai
cp .env.example .env            # Windows PowerShell: copy .env.example .env
# edit .env: set JWT_SECRET_KEY (and ADZUNA_* if you have keys)

docker compose up --build
```

Open:
- App: http://localhost:5173
- API docs (Swagger): http://localhost:8000/docs

The backend container runs migrations, seeds companies, and ingests jobs on first start when the active jobs table is empty. Later restarts skip the initial ingest once jobs exist.
Then, in a **second terminal**, fetch jobs and create an admin:

```bash
docker compose exec backend python -m app.cli ingest
docker compose exec backend python -m app.cli verify --limit 25
docker compose exec backend python -m app.cli create-admin you@example.com
```

### Option B — Run locally without Docker (SQLite, no database install needed)

Prerequisites: **Python 3.11+** and **Node.js 18+**.

**Backend** (terminal 1):

```bash
cd jobpulse-ai
cp .env.example .env                       # Windows: copy .env.example .env
cd backend

python -m venv .venv
source .venv/bin/activate                  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt

alembic upgrade head                       # create tables and seed the company directory
python -m app.cli ingest                   # fetch real jobs (needs internet)
python -m app.cli verify --limit 25        # optional: check links of the first 25 unverified jobs
python -m app.cli create-admin you@example.com   # optional: asks for a password

uvicorn app.main:app --reload --port 8000
```

**Frontend** (terminal 2):

```bash
cd jobpulse-ai/frontend
npm install
npm run dev
```

Open http://localhost:5173. The Vite dev server proxies `/api` to `http://localhost:8000`.

### Using PostgreSQL locally instead of SQLite

```bash
docker run -d --name jobpulse-db -p 5432:5432 -e POSTGRES_USER=jobpulse \
  -e POSTGRES_PASSWORD=jobpulse -e POSTGRES_DB=jobpulse pgvector/pgvector:pg16
```

Add to `.env`: `DATABASE_URL=postgresql+psycopg://jobpulse:jobpulse@localhost:5432/jobpulse`, then run `alembic upgrade head` again.

---

## 4. Everyday commands

| Task | Command (run inside `backend/`) |
|---|---|
| Fetch from all sources | `python -m app.cli ingest` |
| Fetch selected sources | `python -m app.cli ingest --sources remotive,greenhouse` |
| Verify links of unverified jobs | `python -m app.cli verify --limit 50` |
| Reload company directory | `python -m app.cli seed-companies` |
| Create/promote an admin | `python -m app.cli create-admin you@example.com` |
| Run all tests | `pytest` |
| New migration after editing `models.py` | `alembic revision --autogenerate -m "describe change"` then `alembic upgrade head` |

Check what happened in each fetch (as admin): `GET /api/admin/fetch-logs` — shows fetched / new / updated /
duplicate counts, plus the error text for sources that failed or were skipped.

## 5. API credentials

| Service | Needed now? | What to get |
|---|---|---|
| Remotive, Arbeitnow, Greenhouse, Lever | No | Nothing |
| Adzuna | Optional | App ID + App Key from https://developer.adzuna.com |
| JWT secret | Yes | Any long random string |
| Jooble, JSearch, Groq, Redis, Instagram | Later phases | Not used yet |

You never need your Instagram password. When Instagram is added it will use Meta's OAuth flow.

## 6. Trying the filters

All filters combine. Examples (replace the host if needed):

```bash
# Jobs published in the last 24 hours
curl "localhost:8000/api/jobs?posted_within_days=1"

# 0–1 year experience, in India, requiring Python and FastAPI
curl "localhost:8000/api/jobs?experience=0-1&country=India&skills=python,fastapi"

# Remote jobs open to candidates worldwide (not country-restricted)
curl "localhost:8000/api/jobs?workplace_type=remote&remote_scope=worldwide"

# Verified jobs from MNCs, newest first
curl "localhost:8000/api/jobs?verified_only=true&mnc_only=true"

# Include jobs that don't state experience when filtering by experience
curl "localhost:8000/api/jobs?experience=2-4&include_unspecified_experience=true"
```

Experience buckets: `fresher, 0-1, 1-2, 2-4, 4-6, 6-8, 8-10, 10+` (overlap matching: a "3–5 years" job appears in both `2-4` and `4-6`).
The date filter uses the *source's publication date*; jobs without one are excluded from date filters
(and the UI says "publication date not provided by source").

Other endpoints: `GET /api/jobs/{id}`, `/api/jobs/recent`, `/api/jobs/verified`, `/api/jobs/remote`,
`/api/jobs/stats`, `POST /api/jobs/{id}/verify` (login required), `GET/POST /api/companies`,
`POST /api/auth/register|login|refresh`, `GET /api/auth/me`,
admin: `GET /api/admin/statistics|sources|fetch-logs`, `POST /api/admin/ingest`.
Full interactive docs: http://localhost:8000/docs

## 7. Troubleshooting

- **UI shows "The database is empty"** — run `python -m app.cli ingest`.
- **A source shows `partial`/`failed` in fetch-logs** — the `error` field names the failing request; usually a
  network block, a rate limit, or a wrong Greenhouse/Lever identifier.
- **`adzuna` is `skipped`** — set both `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` in `.env`.
- **Port already in use** — change the left side of the port mapping in `docker-compose.yml`, or pass `--port` to uvicorn.
- **Many jobs stay `unverified`** — expected until you run `verify`; some career sites block automated checks
  (403/429), which is reported as unreachable, never as "genuine".
- **Production** — set a strong `JWT_SECRET_KEY`, restrict `CORS_ORIGINS`, and put the API behind HTTPS.

## 8. Next phase

Phase 3 completion + Phase 4/5: Celery + Redis scheduled fetching (15–60 min intervals), richer company
verification, resume upload (PDF/DOCX), Groq-based resume parsing, and pgvector semantic matching with
configurable weights (skills 35 / experience 25 / responsibilities 15 / projects 15 / location 10).
