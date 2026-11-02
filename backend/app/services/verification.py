"""Multi-stage job verification. Every verdict stores the evidence it is based on.

Important: a 200 response alone never makes a job "100% genuine". We only claim what
the evidence supports and keep the wording of statuses conservative.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Job, JobVerificationLog, utcnow

TRUSTED_ATS_DOMAINS = (
    "greenhouse.io", "lever.co", "ashbyhq.com", "workable.com", "myworkdayjobs.com",
    "smartrecruiters.com", "icims.com", "jobvite.com",
)
CLOSED_PHRASES = re.compile(
    r"no longer (?:available|accepting)|position (?:has been|is) filled|job (?:not found|has expired)|"
    r"this job (?:is )?(?:closed|expired)|posting (?:has )?(?:expired|closed)|page not found",
    re.I,
)
FRAUD_PATTERNS = {
    "upfront_payment": re.compile(
        r"registration fee|processing fee|security deposit|pay (?:a |the )?fee|training fee|refundable deposit", re.I),
    "personal_email_contact": re.compile(r"[\w.+-]+@(?:gmail|yahoo|outlook|hotmail|rediffmail)\.\w+", re.I),
    "messaging_app_hiring": re.compile(r"whatsapp|telegram", re.I),
    "payment_transfer": re.compile(r"western union|money ?gram|gift card", re.I),
}


def host_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


_SECOND_LEVEL = {"co", "com", "org", "net", "gov", "ac"}


def base_domain(host: str) -> str:
    """Naive registrable domain: careers.acme.com -> acme.com, jobs.acme.co.uk -> acme.co.uk."""
    parts = [p for p in host.lower().split(".") if p]
    if len(parts) >= 3 and parts[-2] in _SECOND_LEVEL and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def host_matches(host: str, domain: str) -> bool:
    return bool(host and domain) and (host == domain or host.endswith("." + domain))


def same_company_domain(host: str, domain: str) -> bool:
    return bool(host and domain) and base_domain(host) == base_domain(domain)


def verify_job(db: Session, job: Job, client: httpx.Client | None = None) -> Job:
    own_client = client is None
    client = client or httpx.Client(
        timeout=settings.http_timeout_seconds, follow_redirects=True,
        headers={"User-Agent": settings.http_user_agent},
    )
    now = utcnow()
    logs: list[JobVerificationLog] = []

    # Stage 1: company validation (directory membership + domain relationship)
    company = job.company
    company_domains = [host_of(u) for u in (company.website, company.career_url) if u]
    in_directory = company.verification_status in {"seeded", "verified"}
    logs.append(JobVerificationLog(job_id=job.id, stage="company", result="listed" if in_directory else "not_listed",
                                   evidence={"company": company.name, "directory_status": company.verification_status,
                                             "known_domains": company_domains}))

    # Stage 2: application link validation
    link_ok, expired, final_host, status_code, error = False, False, None, None, None
    try:
        resp = client.get(job.application_url)
        status_code = resp.status_code
        final_host = host_of(str(resp.url))
        if status_code in (404, 410):
            expired = True
        elif status_code < 400:
            link_ok = True
            if CLOSED_PHRASES.search(resp.text[:20000]):
                expired, link_ok = True, False
        # 401/403/429 etc.: the site may simply block bots; we do not treat that as proof either way.
    except httpx.HTTPError as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        if own_client:
            client.close()
    logs.append(JobVerificationLog(job_id=job.id, stage="application_link",
                                   result="expired" if expired else ("ok" if link_ok else "unreachable"),
                                   evidence={"url": job.application_url, "status_code": status_code,
                                             "final_host": final_host, "error": error}))

    # Stage 5: fraud signals
    flags = [name for name, pat in FRAUD_PATTERNS.items() if pat.search(f"{job.title}\n{job.description}")]
    hard_flags = [f for f in flags if f in {"upfront_payment", "payment_transfer"}]
    logs.append(JobVerificationLog(job_id=job.id, stage="fraud_check",
                                   result="flagged" if flags else "clear", evidence={"flags": flags}))

    # Decision
    check_host = final_host or host_of(job.application_url)
    on_trusted_ats = any(host_matches(check_host, d) for d in TRUSTED_ATS_DOMAINS)
    on_company_domain = any(same_company_domain(check_host, d) for d in company_domains if d)

    if hard_flags:
        status, score = "suspicious", 10
    elif expired:
        status, score = "expired", 0
        job.is_active = False
    elif link_ok and on_company_domain:
        status, score = "verified_official", 90
    elif link_ok and on_trusted_ats and in_directory:
        status, score = "verified_trusted_ats", 85
    elif link_ok and on_trusted_ats:
        status, score = "verified_trusted_ats", 75
    elif link_ok:
        status, score = "partially_verified", 45
    elif job.verification_status == "verified_trusted_ats" and error is None:
        # Came from the company's own ATS API but the page blocks bots: keep, don't upgrade.
        status, score = job.verification_status, min(job.verification_score or 60, 60)
    else:
        status, score = "unverified", 20
    if flags and status not in {"suspicious", "expired"}:
        score = max(0, score - 20)

    job.verification_status, job.verification_score, job.last_verified_at = status, score, now
    for log in logs:
        db.add(log)
    db.commit()
    return job
