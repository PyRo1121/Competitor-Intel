"""Job tracking collector — monitors hiring velocity as growth signal."""

from datetime import UTC, datetime
from typing import Any

import structlog

from competitor_intel.core.collector import BaseCollector

logger = structlog.getLogger()


class JobTrackingCollector(BaseCollector):
    """Track job postings from AI companies as growth signals.

    Sources:
    - Company career pages (ATS: Greenhouse, Lever, Ashby)
    - LinkedIn company pages
    - Wellfound (AngelList)
    - GitHub Jobs (via repos)

    Hiring velocity = strong growth indicator.
    Role patterns reveal strategic direction.
    """

    def __init__(self):
        super().__init__("job_tracking")

    @property
    def source_type(self) -> str:
        return "job_tracking"

    async def collect(self) -> list[dict[str, Any]]:
        """Collect job posting signals."""
        signals = []

        # Track jobs from known AI companies via their ATS
        try:
            greenhouse_jobs = await self._collect_greenhouse()
            signals.extend(greenhouse_jobs)
        except Exception as e:
            logger.error("greenhouse_error", error=str(e))

        try:
            lever_jobs = await self._collect_lever()
            signals.extend(lever_jobs)
        except Exception as e:
            logger.error("lever_error", error=str(e))

        try:
            ashby_jobs = await self._collect_ashby()
            signals.extend(ashby_jobs)
        except Exception as e:
            logger.error("ashby_error", error=str(e))

        logger.info("job_tracking_complete", total_jobs=len(signals))
        return signals

    async def _collect_greenhouse(self) -> list[dict[str, Any]]:
        """Collect from Greenhouse ATS boards."""
        signals = []

        companies = [
            "cursor",
            "anthropic",
            "perplexity",
            "adept",
            "harvey",
            "runway",
            "elevenlabs",
            "cognition",
            "scaleai",
        ]

        for company in companies:
            try:
                url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true"
                response = await self.fetch(url)
                data = response.json()

                for job in data.get("jobs", [])[:5]:
                    departments = job.get("departments", [])
                    dept_names = [d.get("name", "") for d in departments]

                    signals.append(
                        {
                            "title": f"{company} hiring: {job.get('title', '')}",
                            "summary": f"Department: {', '.join(dept_names)}. "
                            f"Location: {job.get('location', {}).get('name', 'Remote')}",
                            "url": job.get("absolute_url", ""),
                            "source": "greenhouse",
                            "signal_type": "job_posting",
                            "detected_at": datetime.now(UTC).isoformat(),
                            "metadata": {
                                "company": company,
                                "job_title": job.get("title", ""),
                                "department": dept_names,
                                "location": job.get("location", {}).get("name", ""),
                                "ats": "greenhouse",
                                "posting_id": job.get("id"),
                            },
                        }
                    )
            except Exception as e:
                logger.warning("greenhouse_company_error", company=company, error=str(e))

        return signals

    async def _collect_lever(self) -> list[dict[str, Any]]:
        """Collect from Lever ATS boards."""
        signals = []

        companies = ["notion", "linear", "coda", "height", "mem"]

        for company in companies:
            try:
                url = f"https://api.lever.co/v0/postings/{company}?mode=json"
                response = await self.fetch(url)
                data = response.json()

                for job in data[:5]:
                    signals.append(
                        {
                            "title": f"{company} hiring: {job.get('title', '')}",
                            "summary": f"Team: {job.get('categories', {}).get('team', 'N/A')}. "
                            f"Location: {job.get('categories', {}).get('location', 'Remote')}",
                            "url": job.get("hostedUrl", ""),
                            "source": "lever",
                            "signal_type": "job_posting",
                            "detected_at": datetime.now(UTC).isoformat(),
                            "metadata": {
                                "company": company,
                                "job_title": job.get("title", ""),
                                "team": job.get("categories", {}).get("team", ""),
                                "location": job.get("categories", {}).get("location", ""),
                                "ats": "lever",
                                "posting_id": job.get("id"),
                            },
                        }
                    )
            except Exception as e:
                logger.warning("lever_company_error", company=company, error=str(e))

        return signals

    async def _collect_ashby(self) -> list[dict[str, Any]]:
        """Collect from Ashby ATS boards."""
        signals = []

        companies = [
            {"name": "cursor", "id": "cursor"},
            {"name": "anthropic", "id": "anthropic"},
        ]

        for company in companies:
            try:
                url = f"https://jobs.ashbyhq.com/api/non-user-boards?boardId={company['id']}"
                response = await self.fetch(url)
                data = response.json()

                jobs = data.get("jobBoard", {}).get("jobPosts", [])
                for job in jobs[:5]:
                    job_info = job.get("job", {})
                    signals.append(
                        {
                            "title": f"{company['name']} hiring: {job_info.get('title', '')}",
                            "summary": f"Location: {job_info.get('locationName', 'Remote')}",
                            "url": (
                                f"https://jobs.ashbyhq.com/{company['id']}/{job_info.get('id', '')}"
                            ),
                            "source": "ashby",
                            "signal_type": "job_posting",
                            "detected_at": datetime.now(UTC).isoformat(),
                            "metadata": {
                                "company": company["name"],
                                "job_title": job_info.get("title", ""),
                                "location": job_info.get("locationName", ""),
                                "ats": "ashby",
                                "posting_id": job_info.get("id"),
                            },
                        }
                    )
            except Exception as e:
                logger.warning("ashby_company_error", company=company["name"], error=str(e))

        return signals
