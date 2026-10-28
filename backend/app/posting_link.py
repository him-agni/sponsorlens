"""Read a job posting from a link, so people can paste a URL instead of the text.

Greenhouse links go through its public Job Board API. Any other page goes through Tavily Extract,
so the server never fetches arbitrary URLs itself.
"""

import logging

import httpx
from pydantic import BaseModel
from tavily import AsyncTavilyClient

from app import greenhouse
from app.config import settings
from app.normalize import normalize

log = logging.getLogger(__name__)

# Shorter than this, the page is almost certainly a sign-in wall or an error page, not a posting.
MIN_CHARS = 300
MAX_CHARS = 50_000
CANNOT_READ = "Couldn't read a job posting at that link. Some sites, like LinkedIn, need a sign-in; paste the posting's text instead."


class UnreadableLink(Exception):
    """The link didn't give us a posting; the message says what to do instead."""


class LinkedPosting(BaseModel):
    url: str
    title: str | None = None
    company: str | None = None
    # Normalized, ready for the paste box and for /api/analyze.
    text: str


async def read(http: httpx.AsyncClient, url: str) -> LinkedPosting:
    if match := greenhouse.JOB_URL.match(url):
        try:
            job = await greenhouse.fetch_job(http, match["token"], match["id"])
        except httpx.HTTPError as error:
            log.warning("Greenhouse job fetch failed for %s: %s", url, error)
            raise UnreadableLink("Greenhouse has no open job at that link; it may have closed.") from error
        return LinkedPosting(url=url, title=job.title, company=job.company, text=_checked(job.text))
    if not settings.tavily_api_key:
        raise UnreadableLink("Reading links from that site needs a Tavily key; paste the posting's text instead.")
    try:
        reply = await AsyncTavilyClient(api_key=settings.tavily_api_key).extract(
            urls=url, extract_depth="basic", format="text"
        )
    except Exception as error:
        log.warning("Tavily extract failed for %s", url, exc_info=True)
        raise UnreadableLink(CANNOT_READ) from error
    results = reply.get("results") or []
    if not results:
        raise UnreadableLink(CANNOT_READ)
    return LinkedPosting(url=url, text=_checked(results[0].get("raw_content") or ""))


def _checked(text: str) -> str:
    text = normalize(text)
    if len(text) < MIN_CHARS:
        raise UnreadableLink(CANNOT_READ)
    return text[:MAX_CHARS]
