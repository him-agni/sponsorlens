import time
from collections.abc import Awaitable, Callable

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from app import company_context
from app.analyzer import Analyzer
from app.company_context import CompanyContext
from app.config import settings
from app.llm import TokenFactoryModel, make_client
from app.rules import decide
from app.schemas import Analysis, Label, Status, Verdict

app = FastAPI(title="SponsorLens")


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


def get_analyzer() -> Analyzer:
    if not settings.nebius_api_key or not settings.nano_model or not settings.ultra_model:
        raise HTTPException(503, "Set NEBIUS_API_KEY, NANO_MODEL and ULTRA_MODEL in .env")
    return Analyzer(TokenFactoryModel(), settings.nano_model, settings.ultra_model)


def get_context_lookup() -> Callable[[str], Awaitable[CompanyContext | None]]:
    return company_context.lookup


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
    analyzer: Analyzer = Depends(get_analyzer),
    lookup: Callable[[str], Awaitable[CompanyContext | None]] = Depends(get_context_lookup),
) -> AnalyzeResponse:
    analysis = await analyzer.analyze(request.text)
    verdict = decide(analysis, request.status)
    context = None
    if verdict.label == Label.UNCLEAR and analysis.company:
        context = await lookup(analysis.company)
    return AnalyzeResponse(analysis=analysis, verdict=verdict, company_context=context)
