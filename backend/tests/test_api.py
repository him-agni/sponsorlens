import time

import pytest
from fastapi.testclient import TestClient

from app import main
from app.budget import BudgetExceeded
from app.company_context import CompanyContext
from app.config import settings
from app.engine.engine import Engine
from app.engine.fake_model import FakeModel
from app.main import app, get_context_lookup, get_link_reader
from app.posting_link import LinkedPosting, UnreadableLink
from test_analyzer import ScriptedModel


def engine_with(model) -> Engine:
    return Engine(
        model, nano_model="nano", ultra_model="ultra", shards=1, workers=2, queue_capacity=4, model_concurrency=2
    )


@pytest.fixture
def client_for(monkeypatch):
    """Start the app, running its lifespan, on an engine built around the given model."""
    clients = []

    def start(model) -> TestClient:
        monkeypatch.setattr(main, "build_engine", lambda: engine_with(model))
        client = TestClient(app).__enter__()
        clients.append(client)
        return client

    yield start
    for client in clients:
        client.__exit__(None, None, None)
    app.dependency_overrides.clear()


def test_analyze_looks_up_company_only_when_unclear(client_for) -> None:
    looked_up: list[str] = []

    async def fake_lookup(company: str) -> CompanyContext:
        looked_up.append(company)
        return CompanyContext(company=company, query="q", sources=[])

    app.dependency_overrides[get_context_lookup] = lambda: fake_lookup
    client = client_for(ScriptedModel({"company": "Acme", "sentences": []}, {"company": "Acme", "sentences": []}))
    unclear = client.post("/api/analyze", json={"text": "Acme is hiring.", "status": "opt"}).json()
    clear = client.post("/api/analyze", json={"text": "Acme is hiring.", "status": "ead"}).json()

    assert unclear["verdict"]["label"] == "unclear"
    assert unclear["company_context"]["company"] == "Acme"
    assert clear["verdict"]["label"] == "clear"
    assert clear["company_context"] is None
    assert looked_up == ["Acme"]


def test_analyze_returns_every_status_and_the_text_it_checked(client_for) -> None:
    client = client_for(FakeModel(latency=0, seed=1))
    body = client.post("/api/analyze", json={"text": "<p>Acme is hiring.</p><p>We will not sponsor visas.</p>", "status": "ead"}).json()
    assert set(body["verdicts"]) == {"ead", "opt", "h1b", "green_card"}
    assert body["verdicts"]["ead"] == body["verdict"]
    assert body["verdicts"]["opt"]["label"] == "blocked"
    assert body["text"] == "Acme is hiring.\nWe will not sponsor visas."


def test_company_context_endpoint_uses_the_lookup(client_for) -> None:
    async def fake_lookup(company: str) -> CompanyContext:
        return CompanyContext(company=company, query="q", sources=[])

    app.dependency_overrides[get_context_lookup] = lambda: fake_lookup
    client = client_for(ScriptedModel())
    assert client.get("/api/company-context", params={"company": "Acme"}).json()["company"] == "Acme"


def test_analyze_rejects_unknown_status(client_for) -> None:
    client = client_for(ScriptedModel())
    assert client.post("/api/analyze", json={"text": "x", "status": "tourist"}).status_code == 422


def test_failed_model_call_is_a_502(client_for) -> None:
    client = client_for(FakeModel(latency=0, failure_rate=1.0))
    response = client.post("/api/analyze", json={"text": "Acme is hiring.", "status": "ead"})
    assert response.status_code == 502
    assert "didn't answer" in response.json()["detail"]


def test_an_unreadable_reply_asks_for_just_the_job_description(client_for) -> None:
    client = client_for(ScriptedModel("", "", ""))
    response = client.post("/api/analyze", json={"text": "Acme is hiring.", "status": "ead"})
    assert response.status_code == 502
    assert "paste just the job description" in response.json()["detail"]


class SpentModel:
    async def complete(self, model: str, messages: list[dict], think: bool = True) -> str:
        raise BudgetExceeded("today's $1.00 demo budget is spent")


def test_a_spent_budget_is_a_429_that_says_so(client_for) -> None:
    client = client_for(SpentModel())
    response = client.post("/api/analyze", json={"text": "Acme is hiring.", "status": "ead"})
    assert response.status_code == 429
    assert "today's budget" in response.json()["detail"]


def test_the_public_endpoints_share_an_hourly_limit(client_for, monkeypatch) -> None:
    monkeypatch.setattr(settings, "hourly_requests", 2)
    app.dependency_overrides[get_context_lookup] = lambda: lambda company: _none()
    client = client_for(FakeModel(latency=0))
    assert client.post("/api/analyze", json={"text": "Acme is hiring.", "status": "ead"}).status_code == 200
    assert client.get("/api/company-context", params={"company": "Acme"}).status_code == 200
    refused = client.post("/api/analyze", json={"text": "Acme is hiring.", "status": "ead"})
    assert refused.status_code == 429
    assert "busy this hour" in refused.json()["detail"]
    assert client.get("/health").status_code == 200


async def _none() -> None:
    return None


def test_read_link_returns_the_posting_or_says_why_not(client_for) -> None:
    async def fake_read(url: str) -> LinkedPosting:
        if "linkedin" in url:
            raise UnreadableLink("paste the posting's text instead")
        return LinkedPosting(url=url, text="We cannot sponsor visas.")

    app.dependency_overrides[get_link_reader] = lambda: fake_read
    client = client_for(FakeModel())
    read = client.post("/api/read-link", json={"url": "https://jobs.lever.co/acme/abc"})
    assert read.json()["text"] == "We cannot sponsor visas."
    refused = client.post("/api/read-link", json={"url": "https://www.linkedin.com/jobs/view/1"})
    assert refused.status_code == 422
    assert "paste the posting" in refused.json()["detail"]
    assert client.post("/api/read-link", json={"url": "not a link"}).status_code == 422


def test_batches_can_be_switched_off(client_for, monkeypatch) -> None:
    monkeypatch.setattr(settings, "live_batches", False)
    client = client_for(FakeModel())
    assert client.get("/health").json() == {"status": "ok", "live_batches": False}
    response = client.post("/api/batch", json={"companies": ["stripe"]})
    assert response.status_code == 403
    assert "recorded run" in response.json()["detail"]


def test_a_batch_runs_and_reports_verdicts_for_any_status(client_for, monkeypatch) -> None:
    from test_batches import postings_for

    async def fake_board(client, token: str):
        return postings_for(token)

    monkeypatch.setattr(main.greenhouse, "fetch_board", fake_board)
    client = client_for(FakeModel(latency=0.001, seed=2))
    created = client.post("/api/batch", json={"companies": ["stripe", "figma"], "per_company": 3, "status": "opt"})
    assert created.status_code == 202
    url = f"/api/batch/{created.json()['id']}"

    deadline = time.monotonic() + 10
    while not (view := client.get(url).json())["finished"] and time.monotonic() < deadline:
        time.sleep(0.05)
    assert view["progress"] == {"total": 6, "done": 6}
    assert view["status"] == "opt"
    assert client.get(url, params={"status": "green_card"}).json()["status"] == "green_card"
    assert [b["id"] for b in client.get("/api/batches").json()] == [view["id"]]


def test_a_batch_takes_only_preset_companies(client_for) -> None:
    client = client_for(FakeModel())
    response = client.post("/api/batch", json={"companies": ["stripe", "evil-corp"]})
    assert response.status_code == 422
    assert "evil-corp" in response.text
    assert client.get("/api/batch/nope").status_code == 404
    assert "stripe" in client.get("/api/presets").json()["companies"]


def test_without_a_key_the_engine_is_off_but_health_works(monkeypatch) -> None:
    monkeypatch.setattr(settings, "nebius_api_key", "")
    monkeypatch.setattr(settings, "model_backend", "live")
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        response = client.post("/api/analyze", json={"text": "x", "status": "ead"})
        assert response.status_code == 503
        assert "MODEL_BACKEND=fake" in response.json()["detail"]


def test_rehearsal_is_refused_on_the_live_backend(client_for, monkeypatch) -> None:
    monkeypatch.setattr(settings, "model_backend", "live")
    client = client_for(ScriptedModel())
    assert client.post("/api/rehearsal", json={"jobs": 5}).status_code == 409


def test_rehearsal_shows_on_metrics(client_for, monkeypatch) -> None:
    monkeypatch.setattr(settings, "model_backend", "fake")
    client = client_for(FakeModel(latency=0.002, seed=1))
    assert client.post("/api/rehearsal", json={"jobs": 40}).status_code == 202

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        snapshot = client.get("/metrics").json()
        if snapshot["counters"].get("jobs_done", 0) == 40:
            break
        time.sleep(0.05)
    assert snapshot["counters"]["jobs_done"] == 40
    assert snapshot["gauges"]["queue_depth"] == 0
    assert snapshot["gauges"]["shard0_queue_peak"] == 4
    assert snapshot["histograms"]["model_latency_ms"]["count"] > 0
