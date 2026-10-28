import pytest

from app import company_context
from app.config import settings
from app.recent import Recent


class FakeTavily:
    queries: list[str] = []

    def __init__(self, api_key: str) -> None:
        pass

    async def search(self, query: str, **kwargs) -> dict:
        FakeTavily.queries.append(query)
        return {"results": [{"title": "Acme H-1B filings", "url": "https://example.com/acme", "content": "Acme filed 40 LCAs."}]}


class BrokenTavily(FakeTavily):
    async def search(self, query: str, **kwargs) -> dict:
        raise RuntimeError("network down")


@pytest.fixture(autouse=True)
def forget_lookups(monkeypatch) -> None:
    monkeypatch.setattr(company_context, "_found", Recent())


async def test_a_company_is_searched_once(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tavily_api_key", "tvly-test")
    monkeypatch.setattr(company_context, "AsyncTavilyClient", FakeTavily)
    FakeTavily.queries = []
    await company_context.lookup("Acme")
    await company_context.lookup("Acme")
    assert len(FakeTavily.queries) == 1


async def test_lookup_without_a_key_does_nothing(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tavily_api_key", "")
    assert await company_context.lookup("Acme") is None


async def test_lookup_returns_cited_sources(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tavily_api_key", "tvly-test")
    monkeypatch.setattr(company_context, "AsyncTavilyClient", FakeTavily)
    context = await company_context.lookup("Acme")
    assert context.company == "Acme"
    assert context.sources[0].url == "https://example.com/acme"
    assert "Acme" in FakeTavily.queries[-1]


class GenericTavily(FakeTavily):
    async def search(self, query: str, **kwargs) -> dict:
        return {
            "results": [
                {"title": "Top 15 companies that sponsor H1B visas", "url": "https://example.com/top", "content": "Deloitte..."},
                {"title": "Acme Corp H-1B filings", "url": "https://example.com/acme", "content": "40 LCAs."},
            ]
        }


async def test_sources_that_do_not_name_the_company_are_dropped(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tavily_api_key", "tvly-test")
    monkeypatch.setattr(company_context, "AsyncTavilyClient", GenericTavily)
    context = await company_context.lookup("Acme")
    assert [s.url for s in context.sources] == ["https://example.com/acme"]
    assert (await company_context.lookup("Marigold Payments")).sources == []


async def test_lookup_failure_returns_none(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tavily_api_key", "tvly-test")
    monkeypatch.setattr(company_context, "AsyncTavilyClient", BrokenTavily)
    assert await company_context.lookup("Acme") is None
