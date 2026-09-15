"""
Live job listings from free, no-API-key-required public job boards.

Two sources are combined for broader coverage:
  - Remotive  (https://remotive.com/api-documentation)      - remote-first, tech-leaning
  - Arbeitnow (https://www.arbeitnow.com/api/job-board-api) - broader/European job board

Both are genuinely public JSON APIs meant for exactly this kind of use, no
key or account needed. If you want deeper or region-specific coverage, this
is the seam to extend: add another `_fetch_from_x()` function that returns a
list of `Job` and plug it into `search_jobs()`. Adzuna, USAJobs, and Jooble
all offer similar free tiers that just require signing up for a key.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import requests

logger = logging.getLogger("applypilot.job_sources")

REQUEST_TIMEOUT = 12  # seconds; a slow upstream API shouldn't hang the whole search


@dataclass
class Job:
    id: str
    source: str
    title: str
    company: str
    location: str
    url: str
    description: str
    tags: list[str] = field(default_factory=list)
    salary: str | None = None
    posted_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source": self.source,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "url": self.url,
            "description": self.description,
            "tags": self.tags,
            "salary": self.salary,
            "posted_at": self.posted_at,
        }

def _fetch_remotive(query: str) -> list[Job]:
    try:
        resp = requests.get(
            "https://remotive.com/api/remote-jobs",
            params={"search": query} if query else {},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001 - a dead upstream API must not break search
        logger.warning("Remotive fetch failed: %s", exc)
        return []

    jobs = []
    for item in data.get("jobs", [])[:60]:
        jobs.append(
            Job(
                id=f"remotive-{item.get('id')}",
                source="Remotive",
                title=item.get("title", "Untitled role"),
                company=item.get("company_name", "Unknown company"),
                location=item.get("candidate_required_location", "Remote"),
                url=item.get("url", ""),
                description=_strip_html(item.get("description", "")),
                tags=[t.lower() for t in item.get("tags", [])],
                salary=item.get("salary") or None,
                posted_at=item.get("publication_date"),
            )
        )
    return jobs


def _fetch_arbeitnow(query: str) -> list[Job]:
    try:
        resp = requests.get("https://www.arbeitnow.com/api/job-board-api", timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Arbeitnow fetch failed: %s", exc)
        return []

    query_lower = query.lower().strip()
    jobs = []
    for item in data.get("data", [])[:150]:
        title = item.get("title", "Untitled role")
        description = _strip_html(item.get("description", ""))
        if query_lower and query_lower not in title.lower() and query_lower not in description.lower():
            continue
        jobs.append(
            Job(
                id=f"arbeitnow-{item.get('slug', item.get('title', ''))}",
                source="Arbeitnow",
                title=title,
                company=item.get("company_name", "Unknown company"),
                location=item.get("location") or ("Remote" if item.get("remote") else "Not specified"),
                url=item.get("url", ""),
                description=description,
                tags=[t.lower() for t in item.get("tags", [])],
                salary=None,
                posted_at=str(item.get("created_at")) if item.get("created_at") else None,
            )
        )
    return jobs[:60]


def _strip_html(text: str) -> str:
    import re

    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def search_jobs(query: str = "", location: str = "") -> list[Job]:
    """Fetch and merge listings from every source, de-duplicated by (title, company)."""
    all_jobs: list[Job] = []
    all_jobs.extend(_fetch_remotive(query))
    all_jobs.extend(_fetch_arbeitnow(query))

    if location:
        loc_lower = location.lower()
        all_jobs = [j for j in all_jobs if loc_lower in j.location.lower() or "remote" in j.location.lower()]

    seen = set()
    deduped = []
    for job in all_jobs:
        key = (job.title.strip().lower(), job.company.strip().lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(job)
    return deduped

