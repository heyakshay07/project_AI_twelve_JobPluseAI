from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=64)
    full_name: str = Field(default="", max_length=255)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=64)


class RefreshIn(BaseModel):
    refresh_token: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    full_name: str
    role: str


class CompanyIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    website: str | None = None
    career_url: str | None = None
    ats_provider: str | None = None
    ats_identifier: str | None = None
    logo_url: str | None = None
    country: str | None = None
    category: str | None = None
    is_mnc: bool = False


class CompanyOut(CompanyIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    verification_status: str


class VerificationLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    stage: str
    result: str
    evidence: dict
    created_at: datetime


class JobOut(BaseModel):
    id: int
    title: str
    company_id: int
    company_name: str
    company_logo_url: str | None = None
    company_is_mnc: bool = False
    location: str
    country: str | None
    workplace_type: str
    remote_scope: str | None
    employment_type: str | None
    minimum_experience: float | None
    maximum_experience: float | None
    experience_status: str
    salary_min: float | None
    salary_max: float | None
    currency: str | None
    skills: list[str]
    first_published_at: datetime | None
    source_updated_at: datetime | None
    fetched_at: datetime
    last_verified_at: datetime | None
    application_url: str
    source_name: str
    other_sources: list[str] = []
    verification_status: str
    verification_score: int
    is_active: bool
    snippet: str = ""


class JobDetailOut(JobOut):
    description: str
    verification_logs: list[VerificationLogOut] = []


class Page(BaseModel):
    items: list
    total: int
    page: int
    page_size: int


class IngestIn(BaseModel):
    sources: list[str] | None = None
