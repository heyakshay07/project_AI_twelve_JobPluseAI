from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[str] = mapped_column(String(20), default="user")  # user | admin
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    profile: Mapped["UserProfile | None"] = relationship(back_populates="user", uselist=False)


class UserProfile(Base):
    """Per-user job preferences. Resume-derived fields arrive in Phase 5."""

    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    target_titles: Mapped[list] = mapped_column(JSON, default=list)
    preferred_locations: Mapped[list] = mapped_column(JSON, default=list)
    skills: Mapped[list] = mapped_column(JSON, default=list)
    min_experience: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_experience: Mapped[float | None] = mapped_column(Float, nullable=True)
    workplace_preference: Mapped[str | None] = mapped_column(String(30), nullable=True)

    user: Mapped[User] = relationship(back_populates="profile")


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    name_normalized: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    career_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ats_provider: Mapped[str | None] = mapped_column(String(30), nullable=True)  # greenhouse | lever | ...
    ats_identifier: Mapped[str | None] = mapped_column(String(100), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category: Mapped[str | None] = mapped_column(String(60), nullable=True)
    is_mnc: Mapped[bool] = mapped_column(Boolean, default=False)
    # unverified | seeded | verified  (seeded = from curated list, domain not machine-checked)
    verification_status: Mapped[str] = mapped_column(String(20), default="unverified")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    jobs: Mapped[list["Job"]] = relationship(back_populates="company")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("source_name", "external_job_id", name="uq_job_source_external"),
        Index("ix_jobs_active_published", "is_active", "first_published_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    external_job_id: Mapped[str] = mapped_column(String(255))
    source_name: Mapped[str] = mapped_column(String(40), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)

    title: Mapped[str] = mapped_column(String(500))
    title_normalized: Mapped[str] = mapped_column(String(500), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    location: Mapped[str] = mapped_column(String(500), default="")
    country: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    # remote | hybrid | onsite | unknown
    workplace_type: Mapped[str] = mapped_column(String(20), default="unknown", index=True)
    # worldwide | country_restricted | unknown  (only meaningful when workplace_type == remote)
    remote_scope: Mapped[str | None] = mapped_column(String(30), nullable=True)
    employment_type: Mapped[str | None] = mapped_column(String(60), nullable=True)

    minimum_experience: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    maximum_experience: Mapped[float | None] = mapped_column(Float, nullable=True)
    experience_status: Mapped[str] = mapped_column(String(20), default="not_specified")

    salary_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)

    skills: Mapped[list] = mapped_column(JSON, default=list)
    skills_text: Mapped[str] = mapped_column(Text, default="")  # "|python|react|" for portable filtering

    first_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    application_url: Mapped[str] = mapped_column(Text)

    verification_status: Mapped[str] = mapped_column(String(30), default="unverified", index=True)
    verification_score: Mapped[int] = mapped_column(Integer, default=0)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    dedupe_key: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    company: Mapped[Company] = relationship(back_populates="jobs")
    links: Mapped[list["JobSourceLink"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    verification_logs: Mapped[list["JobVerificationLog"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="JobVerificationLog.id.desc()"
    )


class JobSourceLink(Base):
    """Every source that reported a job. Lets duplicates merge while keeping all source URLs."""

    __tablename__ = "job_sources"
    __table_args__ = (UniqueConstraint("source_name", "external_job_id", name="uq_link_source_external"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    source_name: Mapped[str] = mapped_column(String(40))
    external_job_id: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    job: Mapped[Job] = relationship(back_populates="links")


class JobVerificationLog(Base):
    __tablename__ = "job_verification_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    stage: Mapped[str] = mapped_column(String(40))
    result: Mapped[str] = mapped_column(String(40))
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    job: Mapped[Job] = relationship(back_populates="verification_logs")


class FetchLog(Base):
    __tablename__ = "fetch_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_name: Mapped[str] = mapped_column(String(40), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running|ok|partial|failed|skipped
    jobs_fetched: Mapped[int] = mapped_column(Integer, default=0)
    jobs_new: Mapped[int] = mapped_column(Integer, default=0)
    jobs_updated: Mapped[int] = mapped_column(Integer, default=0)
    jobs_duplicate: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
