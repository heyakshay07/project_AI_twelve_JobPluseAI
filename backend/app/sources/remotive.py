from app.services.location import guess_country
from app.services.text import strip_html
from app.sources.base import JobSource, NormalizedJob, parse_dt

_WORLDWIDE = {"worldwide", "anywhere", "anywhere in the world", "global"}


class RemotiveSource(JobSource):
    """https://remotive.com/api/remote-jobs  (keyless).

    Remotive asks consumers to credit them and to fetch no more than a few times a day.
    The job URL points to the Remotive listing, which links onward to the employer's apply page.
    """

    name = "remotive"
    categories = ("software-dev", "data")

    def fetch(self) -> list[NormalizedJob]:
        jobs: list[NormalizedJob] = []
        for category in self.categories:
            try:
                resp = self.client.get("https://remotive.com/api/remote-jobs", params={"category": category})
                resp.raise_for_status()
                for item in resp.json().get("jobs", []):
                    jobs.append(self.parse(item))
            except Exception as exc:  # one failing category must not kill the rest
                self.errors.append(f"remotive[{category}]: {exc}")
        return jobs

    @staticmethod
    def parse(item: dict) -> NormalizedJob:
        loc = (item.get("candidate_required_location") or "").strip()
        if not loc:
            scope = "unknown"
        elif loc.lower() in _WORLDWIDE:
            scope = "worldwide"
        else:
            scope = "country_restricted"
        job_type = (item.get("job_type") or "").replace("_", " ") or None
        return NormalizedJob(
            external_id=str(item["id"]),
            source_name="remotive",
            title=item.get("title", "").strip(),
            company_name=item.get("company_name", "").strip(),
            application_url=item.get("url", ""),
            description=strip_html(item.get("description")),
            location=loc or "Remote",
            country=guess_country(loc) if scope == "country_restricted" else None,
            workplace_type="remote",
            remote_scope=scope,
            employment_type=job_type,
            first_published_at=parse_dt(item.get("publication_date")),
        )
