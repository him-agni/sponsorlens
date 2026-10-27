"""Tavily web context for Unclear verdicts. It is shown beside the verdict and never changes it."""

import logging

from pydantic import BaseModel
from tavily import AsyncTavilyClient

from app.config import settings

log = logging.getLogger(__name__)


class Source(BaseModel):
    title: str
    url: str
    snippet: str


class CompanyContext(BaseModel):
    company: str
    query: str
    sources: list[Source]


_found: dict[str, CompanyContext] = {}


async def lookup(company: str, max_results: int = 3) -> CompanyContext | None:
    """Search the company's H-1B sponsorship history. Returns None without a key or on failure.

    Results are kept for the life of the process, so a company is searched once however many of its
    postings come back Unclear.
    """
    if not settings.tavily_api_key or not company:
        return None
    if company in _found:
        return _found[company]
    query = f"{company} H-1B visa sponsorship history"
    try:
        reply = await AsyncTavilyClient(api_key=settings.tavily_api_key).search(
            query, search_depth="basic", max_results=max_results
        )
    except Exception:
        log.warning("Tavily search failed for %s", company, exc_info=True)
        return None
    sources = [Source(title=r["title"], url=r["url"], snippet=r["content"]) for r in reply.get("results", [])]
    about = [s for s in sources if mentions(s, company)]
    _found[company] = CompanyContext(company=company, query=query, sources=about)
    return _found[company]


def mentions(source: Source, company: str) -> bool:
    """Search often returns generic lists of sponsors; keep only sources that name the company.

    Matches the full name, or its first word when that is distinctive enough (four letters or more).
    """
    text = f"{source.title} {source.url} {source.snippet}".lower()
    name = company.lower().strip()
    first = name.split()[0] if name else ""
    return name in text or (len(first) >= 4 and first in text)
