"""Real postings from Ashby's public job board API (api.ashbyhq.com/posting-api): read-only, no key.

Used the same way as Greenhouse: listed jobs only, held in memory while analyzed, never stored, and
every verdict links back to the posting on jobs.ashbyhq.com.
"""

import re

import httpx

from app.postings import Posting, in_us

BASE_URL = "https://api.ashbyhq.com/posting-api/job-board"

# A company's board, or any page on it: https://jobs.ashbyhq.com/openai, .../openai/<job id>.
BOARD_URL = re.compile(r"^https://jobs\.ashbyhq\.com/(?P<token>[\w.-]+)")
_US_NAMES = {"united states", "united states of america", "usa", "us"}


def is_us(job: dict) -> bool:
    """Ashby gives each location a structured address; a job counts if any location is in the US."""
    locations = [job, *(job.get("secondaryLocations") or [])]
    countries = [((place.get("address") or {}).get("postalAddress") or {}).get("addressCountry") or "" for place in locations]
    if any(countries):
        return any(country.lower() in _US_NAMES for country in countries)
    return in_us([place.get("location") or "" for place in locations])


def _posting(token: str, job: dict) -> Posting:
    text = f"<h2>{job.get('title', '')}</h2>{job.get('descriptionHtml') or ''}"
    # The pay range sits outside the description; adding it lets "at a glance" quote it.
    pay = (job.get("compensation") or {}).get("compensationTierSummary")
    if pay and job.get("shouldDisplayCompensationOnJobPostings"):
        text += f"<p>Compensation: {pay}</p>"
    return Posting(
        source=f"ashby:{token}:{job['id']}",
        company=token,
        title=job.get("title", ""),
        url=job.get("jobUrl", ""),
        location=job.get("location") or "",
        text=text,
    )


def parse_board(token: str, payload: dict) -> list[Posting]:
    """Listed US jobs, oldest first, so the same board gives the same selection on a re-fetch."""
    jobs = (job for job in payload.get("jobs", []) if job.get("isListed", True) and is_us(job))
    return [_posting(token, job) for job in sorted(jobs, key=lambda j: (j.get("publishedAt") or "", j["id"]))]


async def fetch_board(client: httpx.AsyncClient, token: str) -> list[Posting]:
    response = await client.get(f"{BASE_URL}/{token}", params={"includeCompensation": "true"})
    response.raise_for_status()
    return parse_board(token, response.json())


async def has_board(client: httpx.AsyncClient, token: str) -> bool:
    """True if Ashby has a job board by this name. Like Lever, Ashby gives no company name to compare."""
    response = await client.get(f"{BASE_URL}/{token}")
    if response.status_code == 404:
        return False
    response.raise_for_status()
    return True
