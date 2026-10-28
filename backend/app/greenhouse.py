"""Real postings from the Greenhouse Job Board API: public, read-only, no key.

Greenhouse documents these GET endpoints as public ("authentication is not required for any GET
endpoints"). SponsorLens reads only published jobs, keeps the text in memory while it is analyzed,
never stores or redistributes it, and links every verdict back to the original posting.
"""

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

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


# A company's board, or any page on it: https://job-boards.greenhouse.io/stripe, .../stripe/jobs/8172508.
BOARD_URL = re.compile(r"^https://(?:boards|job-boards)\.greenhouse\.io/(?:embed/job_board\?for=)?(?P<token>[\w-]+)")

async def board_name(client: httpx.AsyncClient, token: str) -> str | None:
    """The company name on a board, or None if Greenhouse has no board by that token."""
    response = await client.get(f"{BASE_URL}/{token}")
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json().get("name")


def site_token(url: str) -> str | None:
    """The likely board token for a company's own careers site: www.databricks.com/careers gives databricks."""
    host = (urlsplit(url).hostname or "").lower()
    labels = [label for label in host.split(".") if label not in ("www", "careers", "jobs", "boards")]
    # Only a plain name goes into a Greenhouse API path.
    if len(labels) < 2 or not re.fullmatch(r"[a-z0-9-]+", labels[-2]):
        return None
    return labels[-2]


async def find_board(client: httpx.AsyncClient, url: str) -> str | None:
    """The board token for a Greenhouse board link, or for a company site whose jobs are on Greenhouse.

    For a company site only Greenhouse's API is asked, never the site itself, and the board must carry
    the site's name, so a common word can't land on another company's board.
    """
    if match := BOARD_URL.match(url):
        return match["token"].lower()
    token = site_token(url)
    if not token:
        return None
    name = await board_name(client, token)
    return token if name and _squash(token) in _squash(name) else None


def _squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


# A job's own page on a Greenhouse-hosted board, e.g. https://job-boards.greenhouse.io/stripe/jobs/8172508.
JOB_URL = re.compile(r"^https://(?:boards|job-boards)\.greenhouse\.io/(?P<token>[\w-]+)/jobs/(?P<id>\d+)")


async def fetch_job(client: httpx.AsyncClient, token: str, job_id: str) -> Posting:
    """One job by ID, wherever it is located: someone pasting its link wants it checked."""
    response = await client.get(f"{BASE_URL}/{token}/jobs/{job_id}")
    response.raise_for_status()
    job = response.json()
    return Posting(
        source=f"greenhouse:{token}:{job['id']}",
        company=job.get("company_name") or token,
        title=job.get("title", ""),
        url=job.get("absolute_url", ""),
        location=(job.get("location") or {}).get("name") or "",
        text=job.get("content") or "",
    )
