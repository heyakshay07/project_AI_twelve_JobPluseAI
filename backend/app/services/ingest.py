"""Normalise, de-duplicate and store jobs coming from any source."""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Company, FetchLog, Job, JobSourceLink, JobVerificationLog, utcnow
from app.services.experience import extract_experience
from app.services.location import detect_workplace, guess_country
from app.services.skills import extract_skills, skills_to_text
from app.services.text import make_dedupe_key, normalize, normalize_company
from app.sources.adzuna import AdzunaSource
from app.sources.arbeitnow import ArbeitnowSource
from app.sources.base import JobSource, NormalizedJob
from app.sources.greenhouse import GreenhouseSource
from app.sources.lever import LeverSource
from app.sources.remotive import RemotiveSource

SOURCE_NAMES = ["remotive", "arbeitnow", "adzuna", "greenhouse", "lever"]
SEED_FILE = Path(__file__).resolve().parents[2] / "data" / "companies.seed.json"


def get_or_create_company(db: Session, name: str, website: str | None = None) -> Company:
    key = normalize_company(name)
    company = db.scalar(select(Company).where(Company.name_normalized == key))
    if company is None:
        company = Company(name=name.strip(), name_normalized=key, website=website)
        db.add(company)
        db.flush()
    return company


def seed_companies(db: Session, path: Path = SEED_FILE) -> int:
    entries = json.loads(path.read_text(encoding="utf-8"))
    created = 0
    for e in entries:
        key = normalize_company(e["name"])
        company = db.scalar(select(Company).where(Company.name_normalized == key))
        if company is None:
            company = Company(name=e["name"], name_normalized=key)
            db.add(company)
            created += 1
        for attr in ("website", "career_url", "ats_provider", "ats_identifier", "country", "category", "is_mnc"):
            if attr in e:
                setattr(company, attr, e[attr])
        if company.verification_status in (None, "unverified"):
            company.verification_status = "seeded"
    db.commit()
    return created


def upsert_job(db: Session, nj: NormalizedJob) -> str:
    """Insert or merge one job. Returns 'new' | 'updated' | 'duplicate'."""
    now = utcnow()
    text = f"{nj.title}\n{nj.description}"
    exp = extract_experience(text)
    skills = extract_skills(text)
    country = nj.country or guess_country(nj.location)
    workplace = nj.workplace_type or detect_workplace(nj.title, nj.location, nj.description)

    fields = dict(
        title=nj.title,
        title_normalized=normalize(nj.title),
        description=nj.description,
        location=nj.location,
        country=country,
        workplace_type=workplace,
        remote_scope=nj.remote_scope if workplace == "remote" else None,
        employment_type=nj.employment_type,
        minimum_experience=exp.minimum,
        maximum_experience=exp.maximum,
        experience_status=exp.status,
        salary_min=nj.salary_min,
        salary_max=nj.salary_max,
        currency=nj.currency,
        skills=skills,
        skills_text=skills_to_text(skills),
        first_published_at=nj.first_published_at,
        source_updated_at=nj.source_updated_at,
        fetched_at=now,
    )

    link = db.scalar(
        select(JobSourceLink).where(
            JobSourceLink.source_name == nj.source_name, JobSourceLink.external_job_id == nj.external_id
        )
    )
    if link is not None:
        job = link.job
        if job.source_name == nj.source_name:  # only the primary source may overwrite core fields
            for k, v in fields.items():
                setattr(job, k, v)
            job.application_url = nj.application_url
        else:
            job.fetched_at = now
        job.is_active = True
        link.fetched_at = now
        link.url = nj.application_url
        return "updated"

    company = get_or_create_company(db, nj.company_name, nj.company_website)
    key = make_dedupe_key(nj.company_name, nj.title, nj.location)
    existing = db.scalar(select(Job).where(Job.dedupe_key == key))
    if existing is not None:
        db.add(JobSourceLink(job_id=existing.id, source_name=nj.source_name,
                             external_job_id=nj.external_id, url=nj.application_url, fetched_at=now))
        # Prefer the company's own ATS link over an aggregator link.
        if nj.trusted_ats and existing.verification_status != "verified_trusted_ats":
            existing.application_url = nj.application_url
            existing.source_name = nj.source_name
            existing.external_job_id = nj.external_id
            existing.verification_status = "verified_trusted_ats"
            existing.verification_score = 70
            existing.last_verified_at = now
            _log_ats_provenance(db, existing, nj)
        existing.fetched_at = now
        return "duplicate"

    job = Job(external_job_id=nj.external_id, source_name=nj.source_name, company_id=company.id,
              application_url=nj.application_url, dedupe_key=key, is_active=True, **fields)
    db.add(job)
    db.flush()
    db.add(JobSourceLink(job_id=job.id, source_name=nj.source_name, external_job_id=nj.external_id,
                         url=nj.application_url, fetched_at=now))
    if nj.trusted_ats:
        job.verification_status = "verified_trusted_ats"
        job.verification_score = 70
        job.last_verified_at = now
        _log_ats_provenance(db, job, nj)
    return "new"


def _log_ats_provenance(db: Session, job: Job, nj: NormalizedJob) -> None:
    db.add(JobVerificationLog(
        job_id=job.id,
        stage="source_provenance",
        result="trusted_ats",
        evidence={**nj.evidence, "note": "Fetched directly from the company's own ATS board API.",
                  "company": nj.company_name},
    ))


def build_sources(db: Session) -> dict[str, JobSource]:
    gh = [(c.name, c.ats_identifier) for c in db.scalars(
        select(Company).where(Company.ats_provider == "greenhouse", Company.ats_identifier.is_not(None)))]
    lv = [(c.name, c.ats_identifier) for c in db.scalars(
        select(Company).where(Company.ats_provider == "lever", Company.ats_identifier.is_not(None)))]
    return {
        "remotive": RemotiveSource(),
        "arbeitnow": ArbeitnowSource(),
        "adzuna": AdzunaSource(),
        "greenhouse": GreenhouseSource(gh),
        "lever": LeverSource(lv),
    }


def run_ingest(
    source_names: list[str] | None = None,
    session_factory: Callable[[], Session] = SessionLocal,
    sources: dict[str, JobSource] | None = None,
) -> list[dict]:
    """Fetch the requested sources and store results. Never raises: failures go to fetch_logs."""
    summaries: list[dict] = []
    with session_factory() as db:
        registry = sources if sources is not None else build_sources(db)
        for name in source_names or SOURCE_NAMES:
            source = registry.get(name)
            log = FetchLog(source_name=name)
            db.add(log)
            db.commit()
            if source is None:
                log.status, log.error = "failed", "Unknown source"
            elif not source.configured():
                log.status, log.error = "skipped", "Missing API credentials"
            else:
                try:
                    fetched = source.fetch()
                    log.jobs_fetched = len(fetched)
                    for nj in fetched:
                        if not (nj.title and nj.company_name and nj.application_url):
                            continue
                        try:
                            with db.begin_nested():
                                outcome = upsert_job(db, nj)
                        except Exception as exc:
                            source.errors.append(f"{nj.external_id}: {exc}")
                            continue
                        if outcome == "new":
                            log.jobs_new += 1
                        elif outcome == "updated":
                            log.jobs_updated += 1
                        else:
                            log.jobs_duplicate += 1
                    log.status = "partial" if source.errors else "ok"
                    if source.errors:
                        log.error = "\n".join(source.errors[:20])[:4000]
                except Exception as exc:
                    log.status, log.error = "failed", str(exc)[:4000]
            log.finished_at = utcnow()
            db.commit()
            summaries.append({"source": name, "status": log.status, "fetched": log.jobs_fetched,
                              "new": log.jobs_new, "updated": log.jobs_updated,
                              "duplicate": log.jobs_duplicate, "error": log.error})
    return summaries
