"""Real postings from the Greenhouse Job Board API: public, read-only, no key.

Greenhouse documents these GET endpoints as public ("authentication is not required for any GET
endpoints"). SponsorLens reads only published jobs, keeps the text in memory while it is analyzed,
never stores or redistributes it, and links every verdict back to the original posting.
"""

import re
from dataclasses import dataclass

import httpx

BASE_URL = "https://boards-api.greenhouse.io/v1/boards"

# Board tokens with enough US roles that 10 each gives a 200-posting batch. Checked Oct 27, 2026.
# SpaceX and Scale AI are in the list because their postings carry export-control and clearance terms.
PRESET_COMPANIES = (
    "spacex", "scaleai", "anthropic", "stripe", "databricks", "coinbase", "brex", "reddit", "robinhood",
    "figma", "pinterest", "airbnb", "samsara", "vercel", "duolingo", "gusto", "discord", "datadog",
    "gitlab", "lyft",
)  # fmt: skip

# DE and IN are left out: they are also the country codes for Germany and India ("Berlin, DE").
_STATES = (
    "AL AK AZ AR CA CO CT DC FL GA HI ID IL IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY "
    "NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY"
).split()
_US = re.compile(
    r"United States|\bUSA?\b|\bU\.S\.|"
    r"New York|San Francisco|Seattle|Austin|Boston|Chicago|Los Angeles|Denver|Atlanta|Washington,? D\.?C|"
    rf",\s*(?:{'|'.join(_STATES)})\b"
)


@dataclass(frozen=True)
class Posting:
    source: str
    company: str
    title: str
    url: str
    location: str
    text: str


def is_us(job: dict) -> bool:
    """True if the job's location, or any of its offices, is in the US."""
    places = [(job.get("location") or {}).get("name") or ""]
    places += [office.get("location") or office.get("name") or "" for office in job.get("offices") or []]
    return any(_US.search(place) for place in places)


def parse_board(token: str, payload: dict) -> list[Posting]:
    """US-located jobs, oldest first by ID, so the same board gives the same selection on a re-fetch."""
    jobs = sorted((job for job in payload.get("jobs", []) if is_us(job) and job.get("content")), key=lambda j: j["id"])
    return [
        Posting(
            source=f"greenhouse:{token}:{job['id']}",
            company=job.get("company_name") or token,
            title=job.get("title", ""),
            url=job.get("absolute_url", ""),
            location=(job.get("location") or {}).get("name") or "",
            text=job["content"],
        )
        for job in jobs
    ]


async def fetch_board(client: httpx.AsyncClient, token: str) -> list[Posting]:
    response = await client.get(f"{BASE_URL}/{token}/jobs", params={"content": "true"})
    response.raise_for_status()
    return parse_board(token, response.json())
