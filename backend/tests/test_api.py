import time

import pytest
from fastapi.testclient import TestClient

from app import main
from app.company_context import CompanyContext
from app.config import settings
from app.engine.engine import Engine
from app.engine.fake_model import FakeModel
from app.main import app, get_context_lookup
from test_analyzer import ScriptedModel


def engine_with(model) -> Engine:
    return Engine(model, nano_model="nano", ultra_model="ultra", workers=2, queue_capacity=4, model_concurrency=2)


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


def test_analyze_rejects_unknown_status(client_for) -> None:
    client = client_for(ScriptedModel())
    assert client.post("/api/analyze", json={"text": "x", "status": "tourist"}).status_code == 422


def test_failed_model_call_is_a_502(client_for) -> None:
    client = client_for(FakeModel(latency=0, failure_rate=1.0))
    response = client.post("/api/analyze", json={"text": "Acme is hiring.", "status": "ead"})
    assert response.status_code == 502
    assert "FakeAPIError" in response.json()["detail"]


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
    assert snapshot["gauges"]["queue_depth_peak"] == 4
    assert snapshot["histograms"]["model_latency_ms"]["count"] > 0
