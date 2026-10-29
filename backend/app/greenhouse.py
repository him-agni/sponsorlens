"""Real postings from the Greenhouse Job Board API: public, read-only, no key.

Greenhouse documents these GET endpoints as public ("authentication is not required for any GET
endpoints"). SponsorLens reads only published jobs, keeps the text in memory while it is analyzed,
never stores or redistributes it, and links every verdict back to the original posting.
"""

import re

import httpx

from app.postings import Posting, in_us

BASE_URL = "https://boards-api.greenhouse.io/v1/boards"

# Board tokens with enough US roles that 10 each gives a 200-posting batch. Checked Oct 27, 2026.
# SpaceX and Scale AI are in the list because their postings carry export-control and clearance terms.
PRESET_COMPANIES = (
    "spacex", "scaleai", "anthropic", "stripe", "databricks", "coinbase", "brex", "reddit", "robinhood",
    "figma", "pinterest", "airbnb", "samsara", "vercel", "duolingo", "gusto", "discord", "datadog",
    "gitlab", "lyft",
)  # fmt: skip

# A company's board, or any page on it: https://job-boards.greenhouse.io/stripe, .../stripe/jobs/8172508.
BOARD_URL = re.compile(r"^https://(?:boards|job-boards)\.greenhouse\.io/(?:embed/job_board\?for=)?(?P<token>[\w-]+)")
# A job's own page on a Greenhouse-hosted board, e.g. https://job-boards.greenhouse.io/stripe/jobs/8172508.
JOB_URL = re.compile(r"^https://(?:boards|job-boards)\.greenhouse\.io/(?P<token>[\w-]+)/jobs/(?P<id>\d+)")


def is_us(job: dict) -> bool:
    """True if the job's location, or any of its offices, is in the US."""
    places = [(job.get("location") or {}).get("name") or ""]
    places += [office.get("location") or office.get("name") or "" for office in job.get("offices") or []]
    return in_us(places)


def _posting(token: str, job: dict) -> Posting:
    return Posting(
        source=f"greenhouse:{token}:{job['id']}",
        company=job.get("company_name") or token,
        title=job.get("title", ""),
        url=job.get("absolute_url", ""),
        location=(job.get("location") or {}).get("name") or "",
        text=job.get("content") or "",
    )


def parse_board(token: str, payload: dict) -> list[Posting]:
    """US-located jobs, oldest first by ID, so the same board gives the same selection on a re-fetch."""
    jobs = sorted((job for job in payload.get("jobs", []) if is_us(job) and job.get("content")), key=lambda j: j["id"])
    return [_posting(token, job) for job in jobs]


async def fetch_board(client: httpx.AsyncClient, token: str) -> list[Posting]:
    response = await client.get(f"{BASE_URL}/{token}/jobs", params={"content": "true"})
    response.raise_for_status()
    return parse_board(token, response.json())


async def fetch_job(client: httpx.AsyncClient, token: str, job_id: str) -> Posting:
    """One job by ID, wherever it is located: someone pasting its link wants it checked."""
    response = await client.get(f"{BASE_URL}/{token}/jobs/{job_id}")
    response.raise_for_status()
    return _posting(token, response.json())


async def board_name(client: httpx.AsyncClient, token: str) -> str | None:
    """The company name on a board, or None if Greenhouse has no board by that token."""
    response = await client.get(f"{BASE_URL}/{token}")
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json().get("name")


async def has_board(client: httpx.AsyncClient, token: str) -> bool:
    """True if Greenhouse has a board by this token and its company name contains the token, so a
    common word from a careers site can't land on another company's board."""
    name = await board_name(client, token)
    return bool(name) and _squash(token) in _squash(name)


def _squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())
