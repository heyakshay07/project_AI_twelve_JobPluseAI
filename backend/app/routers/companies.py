from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin
from app.models import Company, Job
from app.schemas import CompanyIn, CompanyOut
from app.services.text import normalize_company

router = APIRouter(prefix="/api/companies", tags=["companies"])


@router.get("")
def list_companies(
    q: str | None = None,
    mnc_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    stmt = select(Company)
    if q:
        stmt = stmt.where(Company.name.ilike(f"%{q.strip()}%"))
    if mnc_only:
        stmt = stmt.where(Company.is_mnc.is_(True))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Company.name).offset((page - 1) * page_size).limit(page_size)).all()
    counts = dict(db.execute(
        select(Job.company_id, func.count()).where(Job.is_active.is_(True)).group_by(Job.company_id)).all())
    items = [{**CompanyOut.model_validate(c).model_dump(), "active_jobs": counts.get(c.id, 0)} for c in rows]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{company_id}", response_model=CompanyOut)
def get_company(company_id: int, db: Session = Depends(get_db)):
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(404, "Company not found")
    return company


@router.post("", response_model=CompanyOut, status_code=201, dependencies=[Depends(require_admin)])
def add_company(body: CompanyIn, db: Session = Depends(get_db)):
    key = normalize_company(body.name)
    if db.scalar(select(Company).where(Company.name_normalized == key)):
        raise HTTPException(409, "Company already exists")
    company = Company(**body.model_dump(), name_normalized=key, verification_status="unverified")
    db.add(company)
    db.commit()
    return company
