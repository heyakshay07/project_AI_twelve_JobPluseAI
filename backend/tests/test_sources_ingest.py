from datetime import datetime, timedelta, timezone

import httpx

from app.models import Company, FetchLog, Job
from app.services.ingest import run_ingest, seed_companies, upsert_job
from app.sources.arbeitnow import ArbeitnowSource
from app.sources.base import JobSource, NormalizedJob, parse_dt
from app.sources.greenhouse import GreenhouseSource
from app.sources.lever import LeverSource
from app.sources.remotive import RemotiveSource


def iso(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def mock_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_parse_dt_variants():
    assert parse_dt("2024-05-01T10:00:00Z").tzinfo is not None
    assert parse_dt(1714557600).year == 2024
    assert parse_dt(1714557600000).year == 2024  # milliseconds (Lever)
    assert parse_dt("garbage") is None and parse_dt(None) is None


def test_remotive_worldwide_vs_restricted():
    base = {"id": 1, "title": "Python Dev", "company_name": "Acme", "url": "https://remotive.com/x",
            "description": "<p>2-4 years of Python</p>", "publication_date": "2024-05-01T10:00:00"}
    worldwide = RemotiveSource.parse({**base, "candidate_required_location": "Worldwide"})
    india = RemotiveSource.parse({**base, "id": 2, "candidate_required_location": "India"})
    assert worldwide.remote_scope == "worldwide"
    assert india.remote_scope == "country_restricted" and india.country == "India"
    assert worldwide.description == "2-4 years of Python"


def test_arbeitnow_filters_non_it_jobs():
    def handler(request):
        if request.url.params.get("page") != "1":
            return httpx.Response(200, json={"data": []})
        return httpx.Response(200, json={"data": [
            {"slug": "a", "title": "Backend Developer", "company_name": "X", "url": "https://a", "location": "Berlin", "remote": False, "tags": [], "job_types": [], "description": "", "created_at": 1714557600},
            {"slug": "b", "title": "Barista", "company_name": "Y", "url": "https://b", "location": "Berlin", "remote": False, "tags": [], "job_types": [], "description": "", "created_at": 1714557600},
        ]})
    jobs = ArbeitnowSource(client=mock_client(handler)).fetch()
    assert [j.title for j in jobs] == ["Backend Developer"]
    assert jobs[0].country == "Germany"


def test_greenhouse_and_lever_parse_and_survive_404():
    def handler(request):
        if "boards-api.greenhouse.io/v1/boards/good" in str(request.url):
            return httpx.Response(200, json={"jobs": [{"id": 7, "title": "Machine Learning Engineer",
                "absolute_url": "https://boards.greenhouse.io/good/jobs/7", "location": {"name": "Remote - US"},
                "content": "&lt;p&gt;3+ years Python&lt;/p&gt;", "updated_at": iso(1), "first_published": iso(2)}]})
        if "api.lever.co/v0/postings/lv" in str(request.url):
            return httpx.Response(200, json=[{"id": "abc", "text": "Software Engineer", "hostedUrl": "https://jobs.lever.co/lv/abc",
                "categories": {"location": "London", "commitment": "Full-time"}, "descriptionPlain": "Fresher friendly", "createdAt": 1714557600000}])
        return httpx.Response(404)

    gh = GreenhouseSource([("Good Co", "good"), ("Missing Co", "missing")], client=mock_client(handler))
    jobs = gh.fetch()
    assert len(jobs) == 1 and jobs[0].trusted_ats and jobs[0].description == "3+ years Python"
    assert any("missing" in e for e in gh.errors)  # graceful failure recorded

    lv = LeverSource([("Lever Co", "lv")], client=mock_client(handler)).fetch()
    assert lv[0].application_url == "https://jobs.lever.co/lv/abc" and lv[0].country == "United Kingdom"


class FakeSource(JobSource):
    name = "fake"

    def __init__(self, jobs, errors=None):
        super().__init__()
        self._jobs, self.errors = jobs, errors or []

    def fetch(self):
        return self._jobs


def nj(**kw):
    defaults = dict(external_id="1", source_name="fake", title="Python Developer", company_name="Acme Inc.",
                    application_url="https://acme.com/jobs/1", description="2-4 years of Python and FastAPI.",
                    location="Pune, India", first_published_at=datetime.now(timezone.utc) - timedelta(days=1))
    defaults.update(kw)
    return NormalizedJob(**defaults)


def test_upsert_extracts_fields_and_dedupes_across_sources(db):
    assert upsert_job(db, nj()) == "new"
    db.commit()
    job = db.query(Job).one()
    assert (job.minimum_experience, job.maximum_experience) == (2, 4)
    assert job.country == "India" and "fastapi" in job.skills and job.verification_status == "unverified"

    # same job, other aggregator, different punctuation -> merged, not duplicated
    assert upsert_job(db, nj(external_id="zz", source_name="adzuna", company_name="ACME, Inc",
                             application_url="https://adzuna/redirect/1")) == "duplicate"
    # same job arrives from the company's own ATS -> link upgrades to the official URL
    assert upsert_job(db, nj(external_id="g1", source_name="greenhouse", trusted_ats=True,
                             application_url="https://boards.greenhouse.io/acme/jobs/1",
                             evidence={"provider": "greenhouse"})) == "duplicate"
    db.commit()
    job = db.query(Job).one()
    assert job.application_url.startswith("https://boards.greenhouse.io")
    assert job.verification_status == "verified_trusted_ats"
    assert {l.source_name for l in job.links} == {"fake", "adzuna", "greenhouse"}
    assert upsert_job(db, nj(description="Updated text")) == "updated"


def test_run_ingest_logs_success_skip_and_failure(session_factory):
    class Boom(JobSource):
        name = "boom"

        def fetch(self):
            raise RuntimeError("API down")

    class NoKey(FakeSource):
        requires_key = True

        def configured(self):
            return False

    sources = {"fake": FakeSource([nj(), nj(external_id="2", title="React Developer")], errors=["one page failed"]),
               "boom": Boom(), "nokey": NoKey([])}
    out = run_ingest(["fake", "boom", "nokey", "nonexistent"], session_factory=session_factory, sources=sources)
    by = {o["source"]: o for o in out}
    assert by["fake"]["status"] == "partial" and by["fake"]["new"] == 2
    assert by["boom"]["status"] == "failed" and "API down" in by["boom"]["error"]
    assert by["nokey"]["status"] == "skipped"
    assert by["nonexistent"]["status"] == "failed"
    with session_factory() as db:
        assert db.query(FetchLog).count() == 4 and db.query(Job).count() == 2


def test_seed_companies_idempotent(db):
    assert seed_companies(db) > 10
    assert seed_companies(db) == 0
    assert {c.verification_status for c in db.query(Company)} == {"seeded"}
    assert db.query(Company).filter(Company.ats_provider == "greenhouse").count() >= 3
