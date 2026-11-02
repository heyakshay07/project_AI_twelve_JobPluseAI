from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

from app.config import settings


@dataclass
class NormalizedJob:
    external_id: str
    source_name: str
    title: str
    company_name: str
    application_url: str
    description: str = ""
    location: str = ""
    country: str | None = None
    workplace_type: str | None = None  # remote | hybrid | onsite | None (unknown)
    remote_scope: str | None = None  # worldwide | country_restricted | unknown
    employment_type: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    currency: str | None = None
    first_published_at: datetime | None = None
    source_updated_at: datetime | None = None
    # True when the job came straight from the company's own ATS board (Greenhouse/Lever).
    trusted_ats: bool = False
    evidence: dict = field(default_factory=dict)
    company_website: str | None = None


def parse_dt(value) -> datetime | None:
    """Parse ISO strings / unix seconds / unix milliseconds into aware UTC datetimes."""
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)):
            seconds = value / 1000 if value > 1e11 else value
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        text = str(value).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, OSError, OverflowError):
        return None


class JobSource:
    name = "base"
    requires_key = False

    def __init__(self, client: httpx.Client | None = None):
        self._client = client
        self.errors: list[str] = []

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=settings.http_timeout_seconds,
                headers={"User-Agent": settings.http_user_agent},
                follow_redirects=True,
            )
        return self._client

    def configured(self) -> bool:
        return True

    def fetch(self) -> list[NormalizedJob]:  # pragma: no cover - interface
        raise NotImplementedError
