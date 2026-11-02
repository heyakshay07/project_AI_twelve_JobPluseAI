from app.services.location import guess_country
from app.services.text import is_it_job, strip_html
from app.sources.base import JobSource, NormalizedJob, parse_dt


class ArbeitnowSource(JobSource):
    """https://www.arbeitnow.com/api/job-board-api (keyless). Mostly Germany/EU roles."""

    name = "arbeitnow"
    max_pages = 3

    def fetch(self) -> list[NormalizedJob]:
        jobs: list[NormalizedJob] = []
        for page in range(1, self.max_pages + 1):
            try:
                resp = self.client.get("https://www.arbeitnow.com/api/job-board-api", params={"page": page})
                resp.raise_for_status()
                items = resp.json().get("data", [])
            except Exception as exc:
                self.errors.append(f"arbeitnow[page {page}]: {exc}")
                break
            if not items:
                break
            for item in items:
                job = self.parse(item)
                if job and is_it_job(job.title, " ".join(item.get("tags") or [])):
                    jobs.append(job)
        return jobs

    @staticmethod
    def parse(item: dict) -> NormalizedJob | None:
        if not item.get("slug") or not item.get("url"):
            return None
        location = item.get("location", "") or ""
        remote = bool(item.get("remote"))
        return NormalizedJob(
            external_id=item["slug"],
            source_name="arbeitnow",
            title=item.get("title", "").strip(),
            company_name=item.get("company_name", "").strip(),
            application_url=item["url"],
            description=strip_html(item.get("description")),
            location=location,
            country=guess_country(location),
            workplace_type="remote" if remote else None,
            remote_scope="unknown" if remote else None,
            employment_type=", ".join(item.get("job_types") or []) or None,
            first_published_at=parse_dt(item.get("created_at")),
        )
