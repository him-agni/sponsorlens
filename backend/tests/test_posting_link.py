import httpx
import pytest

from app import posting_link
from app.config import settings
from app.posting_link import UnreadableLink, direct_link, read

POSTING = (
    "<p>Backend Engineer</p><p>Responsibilities</p><p>" + "You will build payment systems. " * 10 + "</p>"
    "<p>Qualifications</p><p>Five years of experience with Python.</p><p>Benefits</p><p>Health, dental, 401(k).</p>"
    "<p>We cannot sponsor visas.</p>"
)
# What a Wellfound search page reads as: other companies' jobs, none of the words a posting uses.
JOBS_LIST = "<p>Over 130k remote & local startup jobs</p>" + "<p>Acme company logo</p><p>Engineering jobs</p>" * 20


def greenhouse(status: int = 200) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/boards/acme/jobs/123"
        job = {"id": 123, "title": "Backend Engineer", "company_name": "Acme", "content": POSTING}
        return httpx.Response(status, json=job if status == 200 else {})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


class FakeTavily:
    urls: list[str] = []
    content = POSTING

    def __init__(self, api_key: str) -> None:
        pass

    async def extract(self, urls: str, **kwargs) -> dict:
        FakeTavily.urls.append(urls)
        return {"results": [{"url": urls, "raw_content": self.content}], "failed_results": []}


class SignInWall(FakeTavily):
    content = "Sign in to view this job"


class SearchPage(FakeTavily):
    content = JOBS_LIST


class Article(FakeTavily):
    content = POSTING * 100


@pytest.fixture
def tavily(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", "tvly-test")
    monkeypatch.setattr(posting_link, "AsyncTavilyClient", FakeTavily)
    FakeTavily.urls = []


async def test_a_greenhouse_link_reads_the_job_from_its_api(tavily) -> None:
    async with greenhouse() as http:
        posting = await read(http, "https://job-boards.greenhouse.io/acme/jobs/123?gh_src=x")
    assert (posting.title, posting.company) == ("Backend Engineer", "Acme")
    assert posting.text.startswith("Backend Engineer\n")
    assert "<p>" not in posting.text
    assert FakeTavily.urls == []


async def test_a_closed_greenhouse_job_says_so(tavily) -> None:
    async with greenhouse(status=404) as http:
        with pytest.raises(UnreadableLink, match="may have closed"):
            await read(http, "https://boards.greenhouse.io/acme/jobs/123")


async def test_any_other_link_goes_through_tavily(tavily) -> None:
    posting = await read(httpx.AsyncClient(), "https://jobs.lever.co/acme/abc")
    assert FakeTavily.urls == ["https://jobs.lever.co/acme/abc"]
    assert "We cannot sponsor visas." in posting.text


async def test_a_sign_in_wall_is_not_a_posting(tavily, monkeypatch) -> None:
    monkeypatch.setattr(posting_link, "AsyncTavilyClient", SignInWall)
    with pytest.raises(UnreadableLink, match="LinkedIn"):
        await read(httpx.AsyncClient(), "https://www.linkedin.com/jobs/view/1")


async def test_without_a_tavily_key_only_greenhouse_links_work(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tavily_api_key", "")
    with pytest.raises(UnreadableLink, match="Tavily key"):
        await read(httpx.AsyncClient(), "https://jobs.lever.co/acme/abc")


@pytest.mark.parametrize("page", [SearchPage, Article])
async def test_a_page_that_is_not_one_posting_gets_no_verdict(tavily, monkeypatch, page) -> None:
    monkeypatch.setattr(posting_link, "AsyncTavilyClient", page)
    with pytest.raises(UnreadableLink, match="doesn't look like a single job posting"):
        await read(httpx.AsyncClient(), "https://example.com/careers")


async def test_a_search_page_link_is_read_from_the_job_itself(tavily) -> None:
    posting = await read(httpx.AsyncClient(), "https://wellfound.com/jobs?job_listing_slug=4892195-app-developer-177129")
    assert FakeTavily.urls == ["https://wellfound.com/jobs/4892195-app-developer-177129"]
    assert posting.url == "https://wellfound.com/jobs/4892195-app-developer-177129"


def test_direct_links() -> None:
    assert direct_link("https://www.linkedin.com/jobs/search/?currentJobId=123&keywords=x") == (
        "https://www.linkedin.com/jobs/view/123"
    )
    assert direct_link("https://jobs.lever.co/acme/abc") == "https://jobs.lever.co/acme/abc"
