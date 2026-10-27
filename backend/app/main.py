import asyncio
import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app import company_context
from app.company_context import CompanyContext
from app.config import settings
from app.engine.engine import Engine
from app.engine.fake_model import FakeModel
from app.engine.queue import QueueClosed
from app.fixtures import numbered_postings
from app.llm import TokenFactoryModel, make_client
from app.rules import decide
from app.schemas import Analysis, Label, Status, Verdict


def build_engine() -> Engine | None:
    """The live engine needs a key; without one the API still serves /health and explains what to set."""
    if settings.model_backend == "fake":
        model, nano, ultra = FakeModel(latency=settings.fake_latency), "fake-nano", "fake-ultra"
    elif settings.nebius_api_key:
        model, nano, ultra = TokenFactoryModel(), settings.nano_model, settings.ultra_model
    else:
        return None
    return Engine(
        model,
        nano_model=nano,
        ultra_model=ultra,
        workers=settings.workers,
        queue_capacity=settings.queue_capacity,
        model_concurrency=settings.model_concurrency,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.engine = build_engine()
    app.state.background = set()
    if app.state.engine:
        await app.state.engine.start()
    yield
    if app.state.engine:
        await app.state.engine.shutdown(discard_pending=True)


app = FastAPI(title="SponsorLens", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/api/ping-model")
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


@app.get("/metrics")
async def metrics(engine: Engine = Depends(get_engine)) -> dict:
    return {"backend": settings.model_backend, **engine.metrics.snapshot()}


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=50_000)
    status: Status


class AnalyzeResponse(BaseModel):
    analysis: Analysis
    verdict: Verdict
    company_context: CompanyContext | None = None


@app.post("/api/analyze")
async def analyze(
    request: AnalyzeRequest,
    engine: Engine = Depends(get_engine),
    lookup: Callable[[str], Awaitable[CompanyContext | None]] = Depends(get_context_lookup),
) -> AnalyzeResponse:
    try:
        analysis = await engine.analyze(request.text, source="pasted")
    except QueueClosed:
        raise HTTPException(503, "The engine is shutting down")
    except RuntimeError as error:
        raise HTTPException(502, f"The model call failed: {error}")
    verdict = decide(analysis, request.status)
    context = None
    if verdict.label == Label.UNCLEAR and analysis.company:
        context = await lookup(analysis.company)
    return AnalyzeResponse(analysis=analysis, verdict=verdict, company_context=context)


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
