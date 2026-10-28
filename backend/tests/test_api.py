import time
from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.budget import BudgetExceeded
from app.company_context import CompanyContext
from app.config import settings
from app.engine.engine import Engine
from app.engine.fake_model import FakeModel
from app.glance import Fact, Glance
from app.main import app, get_context_lookup, get_glance_reader, get_link_reader
from app.posting_link import LinkedPosting, UnreadableLink
from test_analyzer import ScriptedModel


def engine_with(model) -> Engine:
    return Engine(
        model, nano_model="nano", ultra_model="ultra", shards=1, workers=2, queue_capacity=4, model_concurrency=2
    )


async def no_glance(text: str) -> None:
    return None


@pytest.fixture
def client_for(monkeypatch):
    """Start the app, running its lifespan, on an engine built around the given model.

    The at-a-glance read is stubbed out, so scripted models answer only the verdict's calls."""
    clients = []

    def start(model) -> TestClient:
        monkeypatch.setattr(main, "build_engine", lambda: engine_with(model))
        app.dependency_overrides.setdefault(get_glance_reader, lambda: no_glance)
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


def test_analyze_returns_the_glance_beside_the_verdict(client_for) -> None:
    async def fake_glance(text: str) -> Glance:
        return Glance(facts=[Fact(kind="work_mode", value="Remote", quote="fully remote")])

    app.dependency_overrides[get_glance_reader] = lambda: fake_glance
    client = client_for(FakeModel(latency=0, seed=1))
    body = client.post("/api/analyze", json={"text": "Acme is hiring. This role is fully remote.", "status": "ead"}).json()
    assert body["glance"]["facts"] == [{"kind": "work_mode", "value": "Remote", "quote": "fully remote"}]
    assert body["verdict"]["label"] == "clear"


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
    assert client.get("/health").json() == {"status": "ok", "live": True, "live_batches": False}
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


def fake_boards(monkeypatch, count: int = 12) -> None:
    from test_batches import postings_for

    async def fake_board(client, token: str):
        if token == "nosuchco":
            raise httpx.HTTPStatusError("404", request=httpx.Request("GET", "x"), response=httpx.Response(404))
        return postings_for(token, count)

    async def fake_name(client, token: str):
        return {"acme": "Acme Robotics"}.get(token)

    monkeypatch.setattr(main.greenhouse, "fetch_board", fake_board)
    monkeypatch.setattr(main.greenhouse, "board_name", fake_name)


def test_a_company_careers_page_scans_its_greenhouse_board(client_for, monkeypatch) -> None:
    fake_boards(monkeypatch)
    client = client_for(FakeModel(latency=0))
    started = client.post("/api/scan", json={"url": "https://www.acme.com/company/careers/open-positions"})
    assert started.status_code == 202
    assert started.json()["company"] == "acme"


def test_a_board_scan_checks_matching_jobs_even_with_batches_off(client_for, monkeypatch) -> None:
    fake_boards(monkeypatch)
    monkeypatch.setattr(settings, "live_batches", False)
    monkeypatch.setattr(settings, "scan_limit", 2)
    client = client_for(FakeModel(latency=0.001, seed=2))
    started = client.post(
        "/api/scan", json={"url": "https://job-boards.greenhouse.io/acme", "status": "opt", "keyword": "engineer 1"}
    )
    assert started.status_code == 202
    # "Engineer 1", "Engineer 10" and "Engineer 11" match; the limit keeps two.
    assert started.json() == {"id": started.json()["id"], "company": "acme", "found": 3, "scanning": 2}

    url = f"/api/batch/{started.json()['id']}"
    deadline = time.monotonic() + 10
    while not (view := client.get(url).json())["finished"] and time.monotonic() < deadline:
        time.sleep(0.05)
    assert view["progress"] == {"total": 2, "done": 2}
    assert view["keyword"] == "engineer 1"
    assert all(row["title"].startswith("Engineer 1") for row in view["items"])


def test_a_board_scan_explains_bad_links(client_for, monkeypatch) -> None:
    fake_boards(monkeypatch)
    client = client_for(FakeModel())
    not_greenhouse = client.post("/api/scan", json={"url": "https://example.com/careers"})
    assert not_greenhouse.status_code == 422
    assert "Couldn't find a Greenhouse job board for example.com" in not_greenhouse.json()["detail"]
    assert "a link" in client.post("/api/scan", json={"url": "stripe"}).json()["detail"]
    search = client.post("/api/scan", json={"url": "https://my.greenhouse.io/jobs/search?query=frontend"})
    assert "needs a sign-in" in search.json()["detail"]
    unknown = client.post("/api/scan", json={"url": "https://boards.greenhouse.io/nosuchco"})
    assert "Couldn't find" in unknown.json()["detail"]
    none_match = client.post("/api/scan", json={"url": "https://boards.greenhouse.io/acme", "keyword": "chef"})
    assert 'with "chef" in the title' in none_match.json()["detail"]


def test_a_board_scan_counts_every_job_against_the_hourly_limit(client_for, monkeypatch) -> None:
    fake_boards(monkeypatch)
    monkeypatch.setattr(settings, "scan_limit", 5)
    monkeypatch.setattr(settings, "hourly_requests", 8)
    client = client_for(FakeModel(latency=0))
    assert client.post("/api/scan", json={"url": "https://boards.greenhouse.io/acme"}).status_code == 202
    refused = client.post("/api/scan", json={"url": "https://boards.greenhouse.io/acme"})
    assert refused.status_code == 429


def test_after_the_last_day_nothing_can_spend_credits(client_for, monkeypatch) -> None:
    fake_boards(monkeypatch)
    monkeypatch.setattr(settings, "live_until", date(2026, 12, 15))
    monkeypatch.setattr(main, "demo_over", lambda until: True)
    client = client_for(FakeModel())
    assert client.get("/health").json()["live"] is False
    paid = [
        client.post("/api/analyze", json={"text": "Acme is hiring.", "status": "ead"}),
        client.post("/api/read-link", json={"url": "https://jobs.lever.co/acme/abc"}),
        client.get("/api/company-context", params={"company": "Acme"}),
        client.post("/api/scan", json={"url": "https://boards.greenhouse.io/acme"}),
        client.post("/api/batch", json={"companies": ["stripe"]}),
    ]
    assert [r.status_code for r in paid] == [503] * 5
    assert "ended on December 15, 2026" in paid[0].json()["detail"]
    # Free endpoints keep working, so the web app can show its recorded runs.
    assert client.get("/api/presets").status_code == 200
    assert client.get("/metrics").status_code == 200


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


def test_metrics_report_the_engine(client_for) -> None:
    client = client_for(FakeModel(latency=0, seed=1))
    client.post("/api/analyze", json={"text": "Acme is hiring.", "status": "ead"})
    snapshot = client.get("/metrics").json()
    assert snapshot["counters"]["jobs_done"] == 1
    assert snapshot["gauges"]["queue_depth"] == 0
    assert snapshot["histograms"]["model_latency_ms"]["count"] > 0


def test_oversized_requests_are_refused_unread(client_for) -> None:
    client = client_for(FakeModel())
    response = client.post("/api/analyze", content=b"x" * 300_000, headers={"content-type": "application/json"})
    assert response.status_code == 413


def test_a_failed_scan_lookup_still_counts_against_the_hour(client_for, monkeypatch) -> None:
    """Otherwise anyone could make the server fetch Greenhouse boards without limit."""
    fake_boards(monkeypatch)
    monkeypatch.setattr(settings, "hourly_requests", 1)
    client = client_for(FakeModel())
    assert client.post("/api/scan", json={"url": "https://boards.greenhouse.io/nosuchco"}).status_code == 422
    assert client.post("/api/scan", json={"url": "https://boards.greenhouse.io/acme"}).status_code == 429


def test_dashboard_streams_are_capped(client_for) -> None:
    client = client_for(FakeModel())
    app.state.streams = main.MAX_STREAMS
    assert client.get("/api/stream").status_code == 503
