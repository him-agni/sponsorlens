"""Real postings from Lever's public postings API (api.lever.co/v0/postings): read-only, no key.

Used the same way as Greenhouse: published jobs only, held in memory while analyzed, never stored,
and every verdict links back to the posting on jobs.lever.co.
"""

import re

import httpx

from app.postings import Posting, in_us

BASE_URL = "https://api.lever.co/v0/postings"

# A company's board, or any page on it: https://jobs.lever.co/palantir, .../palantir/<posting id>.
BOARD_URL = re.compile(r"^https://jobs\.lever\.co/(?P<token>[\w.-]+)")
JOB_URL = re.compile(r"^https://jobs\.lever\.co/(?P<token>[\w.-]+)/(?P<id>[0-9a-f-]{36})")


def is_us(posting: dict) -> bool:
    """Lever gives a country code; older postings without one fall back to their location text."""
    if country := posting.get("country"):
        return country == "US"
    categories = posting.get("categories") or {}
    return in_us([categories.get("location") or "", *(categories.get("allLocations") or [])])


def _posting(token: str, posting: dict) -> Posting:
    # The description, then each titled list (responsibilities, requirements...), then the closing
    # section, which is where Lever postings usually say whether they sponsor.
    lists = "".join(f"<h3>{item.get('text', '')}</h3><ul>{item.get('content', '')}</ul>" for item in posting.get("lists") or [])
    text = f"<h2>{posting.get('text', '')}</h2>{posting.get('description') or ''}{lists}{posting.get('additional') or ''}"
    return Posting(
        source=f"lever:{token}:{posting['id']}",
        company=token,
        title=posting.get("text", ""),
        url=posting.get("hostedUrl", ""),
        location=(posting.get("categories") or {}).get("location") or "",
        text=text,
    )


def parse_board(token: str, payload: list[dict]) -> list[Posting]:
    """US jobs, oldest first, so the same board gives the same selection on a re-fetch."""
    postings = sorted((p for p in payload if is_us(p)), key=lambda p: (p.get("createdAt") or 0, p["id"]))
    return [_posting(token, p) for p in postings]


async def fetch_board(client: httpx.AsyncClient, token: str) -> list[Posting]:
    response = await client.get(f"{BASE_URL}/{token}", params={"mode": "json"})
    response.raise_for_status()
    return parse_board(token, response.json())


async def fetch_job(client: httpx.AsyncClient, token: str, job_id: str) -> Posting:
    response = await client.get(f"{BASE_URL}/{token}/{job_id}", params={"mode": "json"})
    response.raise_for_status()
    return _posting(token, response.json())


async def has_board(client: httpx.AsyncClient, token: str) -> bool:
    """True if Lever has a company by this name. Lever gives no company name to compare, so this
    relies on the name matching exactly; the results name the board they came from."""
    response = await client.get(f"{BASE_URL}/{token}", params={"mode": "json", "limit": 1})
    if response.status_code == 404:
        return False
    response.raise_for_status()
    return True
