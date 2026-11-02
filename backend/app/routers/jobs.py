from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import get_current_user
from app.models import Company, Job, User, utcnow
from app.schemas import JobDetailOut, JobOut
from app.services.experience import EXPERIENCE_BUCKETS
from app.services.verification import verify_job

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

VERIFIED_STATUSES = ("verified_official", "verified_trusted_ats")
ROLE_TITLE_TERMS = {
    "frontend": ("frontend", "front end", "ui developer", "web developer"),
    "backend": ("backend", "back end", "server-side developer"),
    "software_developer": ("software developer", "software development engineer", "application developer"),
    "software_engineer": ("software engineer", "software engineering"),
    "ai_engineer": ("ai engineer", "artificial intelligence engineer", "machine learning engineer"),
    "gen_ai": ("genai", "gen ai", "generative ai", "llm engineer"),
    "agentic_ai": ("agentic ai", "agentic", "ai agents", "agent engineer"),
}


class JobFilters:
    """All filters can be combined. Query-string names are the public API contract."""

    def __init__(
        self,
        q: str | None = Query(None, description="Search title or company"),
        role: str | None = Query(None, description="Role category: frontend, backend, software_developer, software_engineer, ai_engineer, gen_ai, agentic_ai"),
        company: str | None = None,
        country: str | None = None,
        location: str | None = Query(None, description="City / free-text location"),
        workplace_type: str | None = Query(None, pattern="^(remote|hybrid|onsite|unknown)$"),
        remote_scope: str | None = Query(None, pattern="^(worldwide|country_restricted|unknown)$"),
        experience: str | None = Query(None, description="fresher, 0-1, 1-2, 2-4, 4-6, 6-8, 8-10, 10+"),
        include_unspecified_experience: bool = False,
        posted_within_days: int | None = Query(None, ge=1, le=365),
        skills: str | None = Query(None, description="Comma separated; ALL must match"),
        source: str | None = None,
        employment_type: str | None = None,
        verified_only: bool = False,
        mnc_only: bool = False,
        sort: str = Query("newest", pattern="^(newest|fetched|verification)$"),
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
    ):
        self.__dict__.update({k: v for k, v in locals().items() if k != "self"})


def build_query(f: JobFilters):
    stmt = select(Job).join(Company).where(Job.is_active.is_(True))
    if f.q:
        like = f"%{f.q.strip()}%"
        stmt = stmt.where(or_(Job.title.ilike(like), Company.name.ilike(like)))
    if f.role:
        terms = ROLE_TITLE_TERMS.get(f.role)
        if terms is None:
            raise HTTPException(422, f"role must be one of {', '.join(ROLE_TITLE_TERMS)}")
        stmt = stmt.where(or_(*(Job.title.ilike(f"%{term}%") for term in terms)))
    if f.company:
        stmt = stmt.where(Company.name.ilike(f"%{f.company.strip()}%"))
    if f.country:
        stmt = stmt.where(Job.country.ilike(f.country.strip()))
    if f.location:
        stmt = stmt.where(Job.location.ilike(f"%{f.location.strip()}%"))
    if f.workplace_type:
        stmt = stmt.where(Job.workplace_type == f.workplace_type)
    if f.remote_scope:
        stmt = stmt.where(Job.workplace_type == "remote", Job.remote_scope == f.remote_scope)
    if f.experience:
        if f.experience not in EXPERIENCE_BUCKETS:
            raise HTTPException(422, f"experience must be one of {', '.join(EXPERIENCE_BUCKETS)}")
        lo, hi = EXPERIENCE_BUCKETS[f.experience]
        overlap = and_(
            Job.minimum_experience <= hi,
            or_(Job.maximum_experience.is_(None), Job.maximum_experience >= lo),
        )
        stmt = stmt.where(or_(overlap, Job.minimum_experience.is_(None)) if f.include_unspecified_experience else overlap)
    if f.posted_within_days:
        # Only jobs that actually carry a publication date can match a recency filter.
        stmt = stmt.where(Job.first_published_at >= utcnow() - timedelta(days=f.posted_within_days))
    if f.skills:
        for skill in [s.strip().lower() for s in f.skills.split(",") if s.strip()]:
            stmt = stmt.where(Job.skills_text.ilike(f"%|{skill}|%"))
    if f.source:
        stmt = stmt.where(Job.source_name == f.source)
    if f.employment_type:
        stmt = stmt.where(Job.employment_type.ilike(f"%{f.employment_type}%"))
    if f.verified_only:
        stmt = stmt.where(Job.verification_status.in_(VERIFIED_STATUSES))
    if f.mnc_only:
        stmt = stmt.where(Company.is_mnc.is_(True))
    return stmt


def to_out(job: Job, detail: bool = False):
    base = dict(
        id=job.id, title=job.title, company_id=job.company_id, company_name=job.company.name,
        company_logo_url=job.company.logo_url, company_is_mnc=job.company.is_mnc,
        location=job.location, country=job.country, workplace_type=job.workplace_type,
        remote_scope=job.remote_scope, employment_type=job.employment_type,
        minimum_experience=job.minimum_experience, maximum_experience=job.maximum_experience,
        experience_status=job.experience_status, salary_min=job.salary_min, salary_max=job.salary_max,
        currency=job.currency, skills=job.skills or [], first_published_at=job.first_published_at,
        source_updated_at=job.source_updated_at, fetched_at=job.fetched_at,
        last_verified_at=job.last_verified_at, application_url=job.application_url,
        source_name=job.source_name,
        other_sources=sorted({l.source_name for l in job.links if l.source_name != job.source_name}),
        verification_status=job.verification_status, verification_score=job.verification_score,
        is_active=job.is_active, snippet=(job.description or "")[:240].replace("\n", " "),
    )
    if detail:
        return JobDetailOut(**base, description=job.description, verification_logs=job.verification_logs)
    return JobOut(**base)


def _paged(db: Session, f: JobFilters):
    stmt = build_query(f)
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    if f.sort == "fetched":
        stmt = stmt.order_by(Job.fetched_at.desc())
    elif f.sort == "verification":
        stmt = stmt.order_by(Job.verification_score.desc(), Job.first_published_at.desc().nulls_last())
    else:
        stmt = stmt.order_by(Job.first_published_at.desc().nulls_last(), Job.fetched_at.desc())
    rows = db.scalars(
        stmt.options(joinedload(Job.company), joinedload(Job.links))
        .offset((f.page - 1) * f.page_size).limit(f.page_size)
    ).unique().all()
    return {"items": [to_out(j) for j in rows], "total": total, "page": f.page, "page_size": f.page_size}


@router.get("")
def list_jobs(f: JobFilters = Depends(), db: Session = Depends(get_db)):
    return _paged(db, f)


@router.get("/recent")
def recent_jobs(f: JobFilters = Depends(), db: Session = Depends(get_db)):
    f.posted_within_days = f.posted_within_days or 7
    return _paged(db, f)


@router.get("/verified")
def verified_jobs(f: JobFilters = Depends(), db: Session = Depends(get_db)):
    f.verified_only = True
    return _paged(db, f)


@router.get("/remote")
def remote_jobs(f: JobFilters = Depends(), db: Session = Depends(get_db)):
    f.workplace_type = "remote"
    return _paged(db, f)


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    now = utcnow()
    active = Job.is_active.is_(True)

    def count(*conds):
        return db.scalar(select(func.count()).select_from(Job).where(active, *conds)) or 0

    by_source = dict(db.execute(
        select(Job.source_name, func.count()).where(active).group_by(Job.source_name)).all())
    return {
        "total_active": count(),
        "last_24h": count(Job.first_published_at >= now - timedelta(hours=24)),
        "last_7d": count(Job.first_published_at >= now - timedelta(days=7)),
        "verified": count(Job.verification_status.in_(VERIFIED_STATUSES)),
        "remote": count(Job.workplace_type == "remote"),
        "remote_worldwide": count(Job.workplace_type == "remote", Job.remote_scope == "worldwide"),
        "without_published_date": count(Job.first_published_at.is_(None)),
        "by_source": by_source,
        "sources": sorted(by_source),
    }


@router.get("/{job_id}", response_model=JobDetailOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.scalar(select(Job).where(Job.id == job_id).options(joinedload(Job.company), joinedload(Job.links)))
    if job is None:
        raise HTTPException(404, "Job not found")
    return to_out(job, detail=True)


@router.post("/{job_id}/verify", response_model=JobDetailOut)
def verify(job_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    verify_job(db, job)
    db.refresh(job)
    return to_out(job, detail=True)
