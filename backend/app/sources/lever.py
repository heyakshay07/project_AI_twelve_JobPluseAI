from app.services.location import detect_workplace, guess_country
from app.services.text import is_it_job
from app.sources.base import JobSource, NormalizedJob, parse_dt


class LeverSource(JobSource):
    """Postings API: https://github.com/lever/postings-api (keyless).

    `sites` is a list of (company_name, lever_site) pairs taken from the companies table.
    """

    name = "lever"

    def __init__(self, sites: list[tuple[str, str]], client=None):
        super().__init__(client)
        self.sites = sites

    def fetch(self) -> list[NormalizedJob]:
        jobs: list[NormalizedJob] = []
        for company, site in self.sites:
            try:
                resp = self.client.get(f"https://api.lever.co/v0/postings/{site}", params={"mode": "json"})
                resp.raise_for_status()
                for item in resp.json():
                    job = self.parse(item, company, site)
                    if job and is_it_job(job.title):
                        jobs.append(job)
            except Exception as exc:
                self.errors.append(f"lever[{site}]: {exc}")
        return jobs

    @staticmethod
    def parse(item: dict, company: str, site: str) -> NormalizedJob | None:
        url = item.get("hostedUrl") or item.get("applyUrl")
        if not url or not item.get("id"):
            return None
        cats = item.get("categories") or {}
        title = item.get("text", "").strip()
        location = cats.get("location") or ""
        desc = item.get("descriptionPlain") or ""
        declared = (item.get("workplaceType") or "").lower()
        workplace = declared if declared in {"remote", "hybrid", "onsite"} else detect_workplace(title, location, desc)
        return NormalizedJob(
            external_id=item["id"],
            source_name="lever",
            title=title,
            company_name=company,
            application_url=url,
            description=desc,
            location=location,
            country=guess_country(location),
            workplace_type=None if workplace == "unknown" else workplace,
            remote_scope="unknown" if workplace == "remote" else None,
            employment_type=cats.get("commitment"),
            first_published_at=parse_dt(item.get("createdAt")),
            trusted_ats=True,
            evidence={"provider": "lever", "site": site},
        )
