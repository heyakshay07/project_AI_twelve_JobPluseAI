from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import require_admin
from app.models import Company, FetchLog, Job, User
from app.schemas import IngestIn
from app.services.ingest import SOURCE_NAMES, run_ingest
from app.sources.adzuna import AdzunaSource

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/sources")
def sources():
    return [
        {"name": n, "requires_key": n == "adzuna",
         "configured": AdzunaSource().configured() if n == "adzuna" else True}
        for n in SOURCE_NAMES
    ]


@router.post("/ingest", status_code=202)
def ingest(body: IngestIn, background: BackgroundTasks):
    names = body.sources or SOURCE_NAMES
    background.add_task(run_ingest, names)
    return {"status": "started", "sources": names}


@router.get("/fetch-logs")
def fetch_logs(limit: int = 50, db: Session = Depends(get_db)):
    rows = db.scalars(select(FetchLog).order_by(FetchLog.id.desc()).limit(min(limit, 200))).all()
    return [
        {"id": r.id, "source": r.source_name, "status": r.status, "started_at": r.started_at,
         "finished_at": r.finished_at, "fetched": r.jobs_fetched, "new": r.jobs_new,
         "updated": r.jobs_updated, "duplicate": r.jobs_duplicate, "error": r.error}
        for r in rows
    ]


@router.get("/statistics")
def statistics(db: Session = Depends(get_db)):
    def n(model, *conds):
        return db.scalar(select(func.count()).select_from(model).where(*conds)) or 0

    by_status = dict(db.execute(select(Job.verification_status, func.count()).group_by(Job.verification_status)).all())
    by_source = dict(db.execute(select(Job.source_name, func.count()).group_by(Job.source_name)).all())
    return {"users": n(User), "companies": n(Company), "jobs": n(Job),
            "active_jobs": n(Job, Job.is_active.is_(True)),
            "jobs_by_verification_status": by_status, "jobs_by_source": by_source,
            "adzuna_configured": bool(settings.adzuna_app_id and settings.adzuna_app_key)}
