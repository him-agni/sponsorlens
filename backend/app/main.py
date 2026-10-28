import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from app import company_context, greenhouse, posting_link
from app.batches import BatchRunner, matching
from app.budget import Budget, BudgetExceeded, HourlyLimit, demo_over
from app.company_context import CompanyContext
from app.config import settings
from app.engine.engine import Engine
from app.engine.fake_model import FakeModel
from app.engine.log import JsonlLogStore
from app.engine.metrics import Metrics
from app.engine.queue import QueueClosed
from app.fixtures import numbered_postings
from app.glance import Glance, read_glance
from app.greenhouse import PRESET_COMPANIES
from app.llm import TokenFactoryModel, make_client
from app.normalize import normalize
from app.posting_link import LinkedPosting, UnreadableLink
from app.rules import decide
from app.schemas import Analysis, Label, Status, Verdict

log = logging.getLogger(__name__)


def build_engine() -> Engine | None:
    """The live engine needs a key; without one the API still serves /health and explains what to set."""
    metrics = Metrics()
    if settings.model_backend == "fake":
        model, nano, ultra = FakeModel(latency=settings.fake_latency, metrics=metrics), "fake-nano", "fake-ultra"
    elif settings.nebius_api_key:
        budget = Budget(metrics, settings.daily_budget_usd, until=settings.live_until)
        model, nano, ultra = TokenFactoryModel(metrics=metrics, budget=budget), settings.nano_model, settings.ultra_model
    else:
        return None
    return Engine(
        model,
        nano_model=nano,
        ultra_model=ultra,
        metrics=metrics,
        shards=settings.shards,
        workers=settings.workers,
        queue_capacity=settings.queue_capacity,
        model_concurrency=settings.model_concurrency,
        log_store=JsonlLogStore(settings.log_path),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = app.state.engine = build_engine()
    app.state.background = set()
    app.state.batches = None
    app.state.hourly = HourlyLimit(settings.hourly_requests)
    http = app.state.http = httpx.AsyncClient(timeout=30, headers={"User-Agent": "SponsorLens/0.1 (hackathon demo)"})
    if engine:
        await engine.start()  # replays the log
        app.state.batches = BatchRunner(engine, lambda token: greenhouse.fetch_board(http, token))
        app.state.batches.resume(engine.replayed)
    yield
    if app.state.batches:
        await app.state.batches.stop()
    if engine:
        await engine.shutdown(discard_pending=True)
    await http.aclose()


app = FastAPI(title="SponsorLens", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
async def health() -> dict:
    # The web app reads these to show recorded runs where live ones would spend credits.
    return {"status": "ok", "live": not demo_over(settings.live_until), "live_batches": settings.live_batches}


def live_demo_open() -> None:
    """After the last live day, nothing in the demo may call a paid service (Token Factory or Tavily)."""
    if demo_over(settings.live_until):
        until = settings.live_until
        raise HTTPException(
            503, f"The live demo ended on {until:%B} {until.day}, {until.year}. The examples and recorded scans still work."
        )


def within_hourly_limit(request: Request) -> None:
    """For the public endpoints that can spend credits."""
    hourly = getattr(request.app.state, "hourly", None)
    if hourly and not hourly.take():
        raise HTTPException(429, "The live demo is busy this hour. The examples still work; try again in a few minutes.")


@app.get("/api/ping-model", dependencies=[Depends(live_demo_open), Depends(within_hourly_limit)])
async def ping_model() -> dict:
    """Phase 0 gate: one round trip to Nemotron on Token Factory."""
    if not settings.nebius_api_key or not settings.nano_model:
        raise HTTPException(503, "Set NEBIUS_API_KEY and NANO_MODEL in .env")

    client = make_client()
    start = time.perf_counter()
    reply = await client.chat.completions.create(
        model=settings.nano_model,
        messages=[{"role": "user", "content": "Reply with exactly: SponsorLens is online."}],
        max_tokens=256,
    )
    latency_ms = round((time.perf_counter() - start) * 1000)

    return {
        "model": reply.model,
        "reply": reply.choices[0].message.content,
        "latency_ms": latency_ms,
        "usage": reply.usage.model_dump() if reply.usage else None,
    }


def get_engine(request: Request) -> Engine:
    engine = request.app.state.engine
    if engine is None:
        raise HTTPException(503, "Set NEBIUS_API_KEY in .env, or MODEL_BACKEND=fake to run without a key")
    return engine


def get_context_lookup() -> Callable[[str], Awaitable[CompanyContext | None]]:
    return company_context.lookup


def get_glance_reader(engine: Engine = Depends(get_engine)) -> Callable[[str], Awaitable[Glance | None]]:
    # Through the engine's guarded model, so the concurrency cap, retries, metrics and budget all apply.
    return lambda text: read_glance(engine.model, engine.nano_model, text)


@app.get("/metrics")
async def metrics(engine: Engine = Depends(get_engine)) -> dict:
    return {"backend": settings.model_backend, **engine.metrics.snapshot()}


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=50_000)
    status: Status


class AnalyzeResponse(BaseModel):
    analysis: Analysis
    verdict: Verdict
    # Every status at once, so the web app switches status without another request.
    verdicts: dict[Status, Verdict]
    # The normalized posting the quotes were checked against, for highlighting them.
    text: str
    company_context: CompanyContext | None = None
    # Location, work mode, experience and so on, each quoted; None if that read failed.
    glance: Glance | None = None


@app.post("/api/analyze", dependencies=[Depends(live_demo_open), Depends(within_hourly_limit)])
async def analyze(
    request: AnalyzeRequest,
    engine: Engine = Depends(get_engine),
    lookup: Callable[[str], Awaitable[CompanyContext | None]] = Depends(get_context_lookup),
    read: Callable[[str], Awaitable[Glance | None]] = Depends(get_glance_reader),
) -> AnalyzeResponse:
    try:
        # The glance never raises, so a failed verdict still fails the request as before.
        analysis, glance = await asyncio.gather(engine.analyze(request.text, source="pasted"), read(request.text))
    except QueueClosed:
        raise HTTPException(503, "The engine is shutting down")
    except RuntimeError as error:
        # The engine reports a job's failure as "<exception name>: <message>".
        if str(error).startswith(BudgetExceeded.__name__):
            raise HTTPException(
                429, "The live demo has spent today's budget. The examples still work, and it resets at midnight UTC."
            )
        # The raw error goes to the log; people see what they can do about it.
        log.warning("Analysis failed: %s", error)
        if str(error).startswith(("ValueError", "ValidationError")):
            raise HTTPException(
                502,
                "The model couldn't finish reading this posting. Try again, or paste just the job description "
                "without the rest of the page.",
            )
        raise HTTPException(502, "The model service didn't answer. Try again in a minute.")
    verdicts = {status: decide(analysis, status) for status in Status}
    verdict = verdicts[request.status]
    context = None
    if verdict.label == Label.UNCLEAR and analysis.company:
        context = await lookup(analysis.company)
    return AnalyzeResponse(
        analysis=analysis,
        verdict=verdict,
        verdicts=verdicts,
        text=normalize(request.text),
        company_context=context,
        glance=glance,
    )


def get_link_reader(request: Request) -> Callable[[str], Awaitable[LinkedPosting]]:
    return lambda url: posting_link.read(request.app.state.http, url)


class LinkRequest(BaseModel):
    url: str = Field(pattern=r"^https?://\S+$", max_length=2000)


@app.post("/api/read-link", dependencies=[Depends(live_demo_open), Depends(within_hourly_limit)])
async def read_link(
    body: LinkRequest, read: Callable[[str], Awaitable[LinkedPosting]] = Depends(get_link_reader)
) -> LinkedPosting:
    """A posting's text from its link, for the paste box. Nothing is analyzed or stored here."""
    try:
        return await read(body.url)
    except UnreadableLink as error:
        raise HTTPException(422, str(error))


@app.get("/api/company-context", dependencies=[Depends(live_demo_open), Depends(within_hourly_limit)])
async def get_company_context(
    company: str = Query(min_length=1, max_length=200),
    lookup: Callable[[str], Awaitable[CompanyContext | None]] = Depends(get_context_lookup),
) -> CompanyContext | None:
    """For a status switched to Unclear in the web app. Web context only; it never changes a verdict."""
    return await lookup(company)


@app.get("/api/stream")
async def stream(request: Request, engine: Engine = Depends(get_engine)) -> StreamingResponse:
    """Server-sent events: a metrics snapshot twice a second, for the live dashboard."""

    async def events():
        while not await request.is_disconnected():
            snapshot = {"backend": settings.model_backend, **engine.metrics.snapshot()}
            yield f"data: {json.dumps(snapshot)}\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


class RehearsalRequest(BaseModel):
    jobs: int = Field(default=200, ge=1, le=2000)


@app.post("/api/rehearsal", status_code=202)
async def rehearsal(request: Request, body: RehearsalRequest, engine: Engine = Depends(get_engine)) -> dict:
    """Push invented postings through the FakeModel engine, to watch backpressure on /metrics at no cost."""
    if settings.model_backend != "fake":
        raise HTTPException(409, "Rehearsals run only with MODEL_BACKEND=fake, so they never spend credits")
    postings = numbered_postings(body.jobs)

    async def submit_all() -> None:
        for i, posting in enumerate(postings):
            await engine.submit(posting, source=f"rehearsal:{i}")

    task = asyncio.create_task(submit_all())
    request.app.state.background.add(task)
    task.add_done_callback(request.app.state.background.discard)
    return {"jobs": body.jobs}


def get_batches(request: Request, engine: Engine = Depends(get_engine)) -> BatchRunner:
    return request.app.state.batches


@app.get("/api/presets")
async def presets() -> dict:
    return {"companies": PRESET_COMPANIES}


class BatchRequest(BaseModel):
    companies: list[str] = Field(default_factory=lambda: list(PRESET_COMPANIES), min_length=1)
    per_company: int = Field(default=10, ge=1, le=25)
    status: Status = Status.H1B

    @field_validator("companies")
    @classmethod
    def only_presets(cls, companies: list[str]) -> list[str]:
        """Batches read only the preset boards, so repeat runs are mostly cache hits."""
        unknown = sorted(set(companies) - set(PRESET_COMPANIES))
        if unknown:
            raise ValueError(f"not in the preset list: {', '.join(unknown)}")
        return list(dict.fromkeys(companies))


@app.post("/api/batch", status_code=202, dependencies=[Depends(live_demo_open)])
async def create_batch(body: BatchRequest, batches: BatchRunner = Depends(get_batches)) -> dict:
    if not settings.live_batches:
        raise HTTPException(403, "Batches are off on the hosted demo, which shows a recorded run instead")
    batch = await batches.create(body.companies, body.per_company, body.status)
    return {"id": batch.id}


class ScanRequest(BaseModel):
    url: str = Field(min_length=1, max_length=500)
    status: Status = Status.H1B
    keyword: str | None = Field(default=None, max_length=60)


def budget_spent(engine: Engine) -> bool:
    gauges = engine.metrics.snapshot()["gauges"]
    limit = gauges.get("budget_limit_micro_usd")
    return limit is not None and gauges["budget_spent_micro_usd"] >= limit


@app.post("/api/scan", status_code=202, dependencies=[Depends(live_demo_open)])
async def scan_board(request: Request, body: ScanRequest, batches: BatchRunner = Depends(get_batches)) -> dict:
    """Scan one company's Greenhouse board: its US jobs, only titles with the keyword if one is given.

    Unlike batches this stays on in the hosted demo, kept small: at most scan_limit jobs, each counted
    against the hourly limit, and every model call still inside the daily budget.
    """
    match = greenhouse.BOARD_URL.match(body.url.strip())
    if not match:
        raise HTTPException(422, "Paste a Greenhouse job board link, like https://job-boards.greenhouse.io/stripe")
    token = match["token"].lower()
    keyword = (body.keyword or "").strip() or None
    try:
        postings = await greenhouse.fetch_board(request.app.state.http, token)
    except httpx.HTTPError:
        raise HTTPException(422, f"Couldn't find a Greenhouse board called \"{token}\". Check the link.")
    found = len(matching(postings, keyword))
    if not found:
        titled = f' with "{keyword}" in the title' if keyword else ""
        raise HTTPException(422, f"No US jobs{titled} on {token}'s board right now.")
    count = min(found, settings.scan_limit)
    if budget_spent(batches.engine):
        raise HTTPException(429, "The live demo has spent today's budget. It resets at midnight UTC.")
    hourly = getattr(request.app.state, "hourly", None)
    if hourly and not hourly.take(count):
        raise HTTPException(429, "The live demo is busy this hour. Try again in a few minutes.")
    batch = await batches.create([token], count, body.status, keyword)
    return {"id": batch.id, "company": token, "found": found, "scanning": count}


@app.get("/api/batch/{batch_id}")
async def get_batch(batch_id: str, status: Status | None = None, batches: BatchRunner = Depends(get_batches)) -> dict:
    batch = batches.batches.get(batch_id)
    if batch is None:
        raise HTTPException(404, "No batch with that ID; the free host forgets batches when it sleeps")
    return batches.view(batch, status)


@app.get("/api/batches")
async def list_batches(batches: BatchRunner = Depends(get_batches)) -> list[dict]:
    """Most recent first, without the per-posting rows."""
    ordered = sorted(batches.batches.values(), key=lambda b: b.created, reverse=True)
    return [{k: v for k, v in batches.view(b).items() if k != "items"} for b in ordered]
