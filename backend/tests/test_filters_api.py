from datetime import datetime, timedelta, timezone

import pytest

from app.models import Company
from app.services.ingest import upsert_job
from tests.test_sources_ingest import nj


def ago(days):
    return datetime.now(timezone.utc) - timedelta(days=days)


@pytest.fixture()
def seeded(client, db):
    rows = [
        nj(external_id="1", title="Python Backend Developer", company_name="Alpha", description="2-4 years Python FastAPI",
           location="Pune, India", first_published_at=ago(0.5)),
        nj(external_id="2", title="GenAI Engineer", company_name="Beta", description="Freshers welcome. LangChain RAG",
           location="Remote", workplace_type="remote", remote_scope="worldwide", first_published_at=ago(2)),
        nj(external_id="3", title="Senior Java Developer", company_name="Gamma", description="8+ years Java Spring Boot",
           location="London, UK", first_published_at=ago(20)),
        nj(external_id="4", title="React Developer", company_name="Delta", description="Build UIs with React.",
           location="Remote - India", workplace_type="remote", remote_scope="country_restricted", first_published_at=None),
        nj(external_id="5", title="Data Scientist", company_name="Epsilon", description="3-5 years", location="Berlin",
           source_name="greenhouse", trusted_ats=True, application_url="https://boards.greenhouse.io/e/jobs/5",
           first_published_at=ago(0.9)),
    ]
    for r in rows:
        upsert_job(db, r)
    db.query(Company).filter(Company.name == "Alpha").update({"is_mnc": True})
    db.commit()
    return client


def titles(resp):
    assert resp.status_code == 200, resp.text
    return {i["title"] for i in resp.json()["items"]}


def test_recency_filter_excludes_undated_jobs(seeded):
    assert titles(seeded.get("/api/jobs", params={"posted_within_days": 1})) == {"Python Backend Developer", "Data Scientist"}
    assert "React Developer" not in titles(seeded.get("/api/jobs", params={"posted_within_days": 30}))
    assert len(seeded.get("/api/jobs/recent").json()["items"]) == 3  # 7-day default


def test_experience_overlap_and_unspecified(seeded):
    assert titles(seeded.get("/api/jobs", params={"experience": "2-4"})) == {"Python Backend Developer", "Data Scientist"}
    assert titles(seeded.get("/api/jobs", params={"experience": "fresher"})) == {"GenAI Engineer"}
    assert titles(seeded.get("/api/jobs", params={"experience": "10+"})) == {"Senior Java Developer"}
    with_unspecified = titles(seeded.get("/api/jobs", params={"experience": "fresher", "include_unspecified_experience": True}))
    assert with_unspecified == {"GenAI Engineer", "React Developer"}
    assert seeded.get("/api/jobs", params={"experience": "99"}).status_code == 422


def test_worldwide_remote_is_not_confused_with_country_restricted(seeded):
    assert titles(seeded.get("/api/jobs", params={"workplace_type": "remote", "remote_scope": "worldwide"})) == {"GenAI Engineer"}
    assert titles(seeded.get("/api/jobs", params={"remote_scope": "country_restricted"})) == {"React Developer"}
    assert titles(seeded.get("/api/jobs/remote")) == {"GenAI Engineer", "React Developer"}


def test_combined_filters_skills_country_verified_mnc(seeded):
    assert titles(seeded.get("/api/jobs", params={"skills": "python,fastapi"})) == {"Python Backend Developer"}
    assert titles(seeded.get("/api/jobs", params={"country": "India", "experience": "2-4"})) == {"Python Backend Developer"}
    assert titles(seeded.get("/api/jobs/verified")) == {"Data Scientist"}
    assert titles(seeded.get("/api/jobs", params={"mnc_only": True})) == {"Python Backend Developer"}
    assert titles(seeded.get("/api/jobs", params={"q": "alpha"})) == {"Python Backend Developer"}


def test_pagination_detail_and_original_link_preserved(seeded):
    page = seeded.get("/api/jobs", params={"page_size": 2, "page": 2}).json()
    assert page["total"] == 5 and len(page["items"]) == 2
    ds = next(i for i in seeded.get("/api/jobs", params={"q": "Data Scientist"}).json()["items"])
    detail = seeded.get(f"/api/jobs/{ds['id']}").json()
    assert detail["application_url"] == "https://boards.greenhouse.io/e/jobs/5"
    assert detail["verification_logs"][0]["stage"] == "source_provenance"
    assert seeded.get("/api/jobs/9999").status_code == 404


def test_stats(seeded):
    s = seeded.get("/api/jobs/stats").json()
    assert s["total_active"] == 5 and s["last_24h"] == 2 and s["verified"] == 1
    assert s["remote_worldwide"] == 1 and s["without_published_date"] == 1
