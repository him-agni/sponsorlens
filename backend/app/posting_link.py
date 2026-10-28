"""Read a job posting from a link, so people can paste a URL instead of the text.

Greenhouse links go through its public Job Board API. Any other page goes through Tavily Extract,
so the server never fetches arbitrary URLs itself.
"""

import logging
from urllib.parse import parse_qs, urlsplit

import httpx
from pydantic import BaseModel
from tavily import AsyncTavilyClient

from app import greenhouse
from app.config import settings
from app.normalize import normalize

log = logging.getLogger(__name__)

# Shorter than this, the page is almost certainly a sign-in wall or an error page, not a posting.
MIN_CHARS = 300
# Real postings ran 4,600 to 8,500 characters; a page this long is an article or a site, not one job.
MAX_CHARS = 40_000
# Words nearly every posting uses. On Oct 28 real postings had 6 to 13 of them; a Wellfound search
# page, a jobs list and a company home page had 1 to 3. A wrong page must never get a verdict.
MARKERS = (
    "responsibilit", "qualification", "requirement", "experience", "about the job", "about the role",
    "you will", "you'll", "skills", "benefits", "salary", "compensation", "full time", "full-time",
    "job description", "what we're looking for", "who you are",
)  # fmt: skip
MIN_MARKERS = 4
CANNOT_READ = "Couldn't read a job posting at that link. Some sites, like LinkedIn, need a sign-in; paste the posting's text instead."
NOT_A_POSTING = (
    "That link doesn't look like a single job posting; it may be a search page or a list of jobs. "
    "Open the job itself and copy its link, or paste the posting's text."
)


class UnreadableLink(Exception):
    """The link didn't give us a posting; the message says what to do instead."""


class LinkedPosting(BaseModel):
    url: str
    title: str | None = None
    company: str | None = None
    # Normalized, ready for the paste box and for /api/analyze.
    text: str


async def read(http: httpx.AsyncClient, url: str) -> LinkedPosting:
    url = direct_link(url)
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
            # Advanced reads pages that render in the browser; on Wellfound, basic dropped the
            # "Visa Sponsorship: Not Available" label and every bullet list.
            urls=url, extract_depth="advanced", format="text"
        )
    except Exception as error:
        log.warning("Tavily extract failed for %s", url, exc_info=True)
        raise UnreadableLink(CANNOT_READ) from error
    results = reply.get("results") or []
    if not results:
        raise UnreadableLink(CANNOT_READ)
    return LinkedPosting(url=url, text=_checked(results[0].get("raw_content") or ""))


def direct_link(url: str) -> str:
    """Some boards show a job in a pop-up over a search page, whose own text is a list of other jobs.
    Their links carry the job's ID, which gives the job's own page."""
    parts = urlsplit(url)
    host = (parts.hostname or "").removeprefix("www.")
    query = parse_qs(parts.query)
    if host == "wellfound.com" and (slug := query.get("job_listing_slug")):
        return f"https://wellfound.com/jobs/{slug[0]}"
    if host == "linkedin.com" and (job_id := query.get("currentJobId")):
        return f"https://www.linkedin.com/jobs/view/{job_id[0]}"
    return url


def _checked(text: str) -> str:
    text = normalize(text)
    if len(text) < MIN_CHARS:
        raise UnreadableLink(CANNOT_READ)
    lowered = text.lower()
    if len(text) > MAX_CHARS or sum(marker in lowered for marker in MARKERS) < MIN_MARKERS:
        raise UnreadableLink(NOT_A_POSTING)
    return text
