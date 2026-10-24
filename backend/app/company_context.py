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


async def lookup(company: str, max_results: int = 3) -> CompanyContext | None:
    """Search the company's H-1B sponsorship history. Returns None without a key or on failure."""
    if not settings.tavily_api_key or not company:
        return None
    query = f"{company} H-1B visa sponsorship history"
    try:
        reply = await AsyncTavilyClient(api_key=settings.tavily_api_key).search(
            query, search_depth="basic", max_results=max_results
        )
    except Exception:
        log.warning("Tavily search failed for %s", company, exc_info=True)
        return None
    sources = [Source(title=r["title"], url=r["url"], snippet=r["content"]) for r in reply.get("results", [])]
    return CompanyContext(company=company, query=query, sources=sources)
