from app.services.location import detect_workplace, guess_country
from app.services.text import is_it_job, strip_html
from app.sources.base import JobSource, NormalizedJob, parse_dt


class GreenhouseSource(JobSource):
    """Public Job Board API: https://developers.greenhouse.io/job-board.html (keyless).

    `boards` is a list of (company_name, board_token) pairs taken from the companies table.
    """

    name = "greenhouse"

    def __init__(self, boards: list[tuple[str, str]], client=None):
        super().__init__(client)
        self.boards = boards

    def fetch(self) -> list[NormalizedJob]:
        jobs: list[NormalizedJob] = []
        for company, token in self.boards:
            try:
                resp = self.client.get(
                    f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs", params={"content": "true"}
                )
                resp.raise_for_status()
                for item in resp.json().get("jobs", []):
                    job = self.parse(item, company, token)
                    if job and is_it_job(job.title):
                        jobs.append(job)
            except Exception as exc:
                self.errors.append(f"greenhouse[{token}]: {exc}")
        return jobs

    @staticmethod
    def parse(item: dict, company: str, token: str) -> NormalizedJob | None:
        if not item.get("absolute_url"):
            return None
        title = item.get("title", "").strip()
        location = (item.get("location") or {}).get("name", "") or ""
        desc = strip_html(item.get("content"))
        workplace = detect_workplace(title, location, desc)
        return NormalizedJob(
            external_id=str(item["id"]),
            source_name="greenhouse",
            title=title,
            company_name=company,
            application_url=item["absolute_url"],
            description=desc,
            location=location,
            country=guess_country(location),
            workplace_type=None if workplace == "unknown" else workplace,
            remote_scope="unknown" if workplace == "remote" else None,
            first_published_at=parse_dt(item.get("first_published")),
            source_updated_at=parse_dt(item.get("updated_at")),
            trusted_ats=True,
            evidence={"provider": "greenhouse", "board_token": token},
        )
