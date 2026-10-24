"""Phase 0 in one command: keys, model IDs, a ping to each model, rate limits, JSON mode and Tavily.

Run from backend/: uv run python -m scripts.check_setup
The output is written to be pasted into FEEDBACK.md.
"""

import asyncio
import json
import sys
import time

from openai import APIError

from app import company_context
from app.config import settings
from app.llm import make_client

RATE_HEADERS = ["x-ratelimit-limit-requests", "x-ratelimit-limit-tokens"]


async def ping(client, model: str, **extra) -> dict:
    start = time.perf_counter()
    raw = await client.chat.completions.with_raw_response.create(
        model=model,
        messages=[{"role": "user", "content": "Reply with exactly: SponsorLens is online."}],
        max_tokens=1024,
        temperature=0,
        **extra,
    )
    reply = raw.parse()
    message = reply.choices[0].message
    return {
        "latency_ms": round((time.perf_counter() - start) * 1000),
        "content": (message.content or "").strip(),
        "extra_fields": sorted((message.model_extra or {}).keys()),
        "usage": reply.usage.model_dump(include={"prompt_tokens", "completion_tokens"}) if reply.usage else None,
        "limits": {h: raw.headers.get(h) for h in RATE_HEADERS},
    }


async def json_mode(client, model: str) -> str:
    try:
        reply = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": 'Reply with a JSON object: {"ok": true}'}],
            response_format={"type": "json_object"},
            max_tokens=1024,
            temperature=0,
        )
    except APIError as error:
        return f"rejected ({error.status_code}: {error.message})"
    content = reply.choices[0].message.content or ""
    try:
        json.loads(content)
    except ValueError:
        return f"accepted, but the reply was not pure JSON: {content[:120]!r}"
    return "accepted, reply was valid JSON"


async def main() -> int:
    missing = [name for name in ("nebius_api_key", "tavily_api_key") if not getattr(settings, name)]
    if missing:
        print(f"Missing in .env: {', '.join(n.upper() for n in missing)}")
        if "nebius_api_key" in missing:
            return 2

    client = make_client()
    available = {m.id for m in (await client.models.list()).data}
    print("## Setup check\n")
    print(f"- Nemotron models on this key: {', '.join(sorted(m for m in available if 'nemotron' in m.lower()))}")

    ok = True
    for role, model in (("Nano", settings.nano_model), ("Ultra", settings.ultra_model)):
        if model not in available:
            print(f"- {role}: {model} is NOT available on this key")
            ok = False
            continue
        try:
            result = await ping(client, model)
        except APIError as error:
            print(f"- {role}: {model} failed ({error.status_code}: {error.message})")
            ok = False
            continue
        print(f"- {role}: {model}")
        print(f"  - reply: {result['content'][:200]!r}")
        print(f"  - latency {result['latency_ms']} ms, usage {result['usage']}")
        print(f"  - rate limits: {result['limits']}")
        if result["extra_fields"]:
            print(f"  - extra message fields (reasoning?): {result['extra_fields']}")
        if "<think>" in result["content"]:
            print("  - reasoning arrives inline in <think> tags")
        print(f"  - JSON mode (response_format json_object): {await json_mode(client, model)}")

    if settings.tavily_api_key:
        context = await company_context.lookup("Microsoft")
        print(f"- Tavily: {'OK, ' + str(len(context.sources)) + ' sources' if context and context.sources else 'FAILED'}")
        ok &= bool(context and context.sources)

    print(f"\nPhase 0 model path: {'OK' if ok else 'NOT OK'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
