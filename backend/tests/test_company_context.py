from fastapi.testclient import TestClient

from app import company_context
from app.config import settings
from app.main import app


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


async def test_lookup_failure_returns_none(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tavily_api_key", "tvly-test")
    monkeypatch.setattr(company_context, "AsyncTavilyClient", BrokenTavily)
    assert await company_context.lookup("Acme") is None


def test_ping_model_without_a_key_explains_what_to_set(monkeypatch) -> None:
    monkeypatch.setattr(settings, "nebius_api_key", "")
    response = TestClient(app).get("/api/ping-model")
    assert response.status_code == 503
    assert "NEBIUS_API_KEY" in response.json()["detail"]
