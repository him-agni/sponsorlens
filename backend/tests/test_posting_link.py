import httpx
import pytest

from app import posting_link
from app.config import settings
from app.posting_link import UnreadableLink, read

POSTING = "<p>Backend Engineer</p><p>" + "You will build payment systems. " * 20 + "</p><p>We cannot sponsor visas.</p>"


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
