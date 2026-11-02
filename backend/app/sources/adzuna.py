import time

from app.config import settings
from app.services.location import detect_workplace
from app.services.text import strip_html
from app.sources.base import JobSource, NormalizedJob, parse_dt

COUNTRY_NAMES = {
    "in": "India", "gb": "United Kingdom", "us": "United States", "ca": "Canada", "de": "Germany",
    "au": "Australia", "sg": "Singapore", "fr": "France", "nl": "Netherlands",
}


class AdzunaSource(JobSource):
    """https://developer.adzuna.com  (needs ADZUNA_APP_ID + ADZUNA_APP_KEY).

    Adzuna's `redirect_url` is an Adzuna tracking link that forwards to the original advert,
    so jobs from this source stay `unverified` until the link is checked.
    """

    name = "adzuna"
    requires_key = True

    def configured(self) -> bool:
        return bool(settings.adzuna_app_id and settings.adzuna_app_key)

    def fetch(self) -> list[NormalizedJob]:
        countries = [c.strip().lower() for c in settings.adzuna_countries.split(",") if c.strip()]
        queries = [q.strip() for q in settings.adzuna_queries.split(",") if q.strip()]
        jobs: list[NormalizedJob] = []
        for country in countries:
            for query in queries:
                try:
                    resp = self.client.get(
                        f"https://api.adzuna.com/v1/api/jobs/{country}/search/1",
                        params={
                            "app_id": settings.adzuna_app_id,
                            "app_key": settings.adzuna_app_key,
                            "results_per_page": 50,
                            "what": query,
                            "max_days_old": settings.adzuna_max_days_old,
                            "sort_by": "date",
                            "content-type": "application/json",
                        },
                    )
                    resp.raise_for_status()
                    for item in resp.json().get("results", []):
                        jobs.append(self.parse(item, country))
                except Exception as exc:
                    self.errors.append(f"adzuna[{country}/{query}]: {exc}")
                time.sleep(0.4)  # stay well under the free-tier rate limit
        return jobs

    @staticmethod
    def parse(item: dict, country_code: str) -> NormalizedJob:
        title = item.get("title", "").strip()
        desc = strip_html(item.get("description"))
        location = (item.get("location") or {}).get("display_name", "")
        workplace = detect_workplace(title, location, desc)
        contract = " ".join(filter(None, [item.get("contract_time", ""), item.get("contract_type", "")]))
        return NormalizedJob(
            external_id=str(item["id"]),
            source_name="adzuna",
            title=title,
            company_name=((item.get("company") or {}).get("display_name") or "").strip(),
            application_url=item.get("redirect_url", ""),
            description=desc,
            location=location,
            country=COUNTRY_NAMES.get(country_code),
            workplace_type=None if workplace == "unknown" else workplace,
            remote_scope="unknown" if workplace == "remote" else None,
            employment_type=contract.replace("_", " ").strip() or None,
            salary_min=item.get("salary_min"),
            salary_max=item.get("salary_max"),
            first_published_at=parse_dt(item.get("created")),
        )
