import httpx

from app.models import Company, Job
from app.services.ingest import upsert_job
from app.services.verification import verify_job
from tests.test_sources_ingest import mock_client, nj


def make_job(db, **kw):
    upsert_job(db, nj(**kw))
    db.commit()
    return db.query(Job).order_by(Job.id.desc()).first()


def test_official_domain_is_verified_official(db):
    job = make_job(db, application_url="https://careers.acme.com/jobs/1")
    job.company.website = "https://www.acme.com"
    db.commit()
    verify_job(db, job, client=mock_client(lambda r: httpx.Response(200, text="Apply now")))
    assert job.verification_status == "verified_official" and job.verification_score >= 90
    stages = {l.stage: l.result for l in job.verification_logs}
    assert stages["application_link"] == "ok" and stages["fraud_check"] == "clear"


def test_trusted_ats_domain(db):
    job = make_job(db, application_url="https://boards.greenhouse.io/acme/jobs/1")
    verify_job(db, job, client=mock_client(lambda r: httpx.Response(200, text="ok")))
    assert job.verification_status == "verified_trusted_ats"


def test_generic_200_is_only_partially_verified(db):
    job = make_job(db, application_url="https://random-board.example/jobs/1")
    verify_job(db, job, client=mock_client(lambda r: httpx.Response(200, text="ok")))
    assert job.verification_status == "partially_verified" and job.verification_score < 60


def test_404_and_closed_text_mark_expired_and_inactive(db):
    job = make_job(db)
    verify_job(db, job, client=mock_client(lambda r: httpx.Response(404)))
    assert job.verification_status == "expired" and job.is_active is False

    job2 = make_job(db, external_id="2", title="Other Dev")
    verify_job(db, job2, client=mock_client(lambda r: httpx.Response(200, text="Sorry, this job is no longer available")))
    assert job2.verification_status == "expired"


def test_fraud_signals_mark_suspicious(db):
    job = make_job(db, description="Pay a registration fee of Rs 2000 to confirm. Contact hr.jobs@gmail.com on WhatsApp")
    verify_job(db, job, client=mock_client(lambda r: httpx.Response(200, text="ok")))
    assert job.verification_status == "suspicious"
    flags = next(l for l in job.verification_logs if l.stage == "fraud_check").evidence["flags"]
    assert "upfront_payment" in flags and "personal_email_contact" in flags


def test_unreachable_link_stays_unverified(db):
    def boom(request):
        raise httpx.ConnectError("no route")
    job = make_job(db)
    verify_job(db, job, client=mock_client(boom))
    assert job.verification_status == "unverified"
    assert next(l for l in job.verification_logs if l.stage == "application_link").result == "unreachable"


def test_verify_endpoint_requires_login(client):
    assert client.post("/api/jobs/1/verify").status_code == 401
