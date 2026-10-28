"""Benchmark the engine on FakeModel with latency drawn from the live Nemotron run. Costs nothing.

Run from backend/: uv run python -m scripts.bench [--scale 100] [--runs 3]

Model calls sleep for a lognormal sample fitted to the Oct 27 live run (p50 6.4 s, p95 79 s, max 101 s),
divided by --scale so a run takes seconds. Times are reported scaled back up to real time. A few calls
take ten times the median, so each setting runs --runs times with different seeds and the median is
reported. Results and what they mean: docs/bench.md.
"""

import argparse
import asyncio
import math
import random
import statistics
import time

from app.engine.engine import Engine
from app.engine.fake_model import FakeModel
from app.engine.jobs import Job, JobState
from app.fixtures import numbered_postings

# Lognormal through the live run's median and 95th percentile; capped at its slowest call.
P50, P95, MAX = 6.4, 79.0, 101.0
MU, SIGMA = math.log(P50), (math.log(P95) - math.log(P50)) / 1.645
# The live run: 200 postings, 303 model calls, $0.30, about 12.5 minutes at 8 concurrent calls.
LIVE_COST_PER_POSTING = 0.30 / 200
HOT = "Long posting."


class LiveLikeModel:
    """FakeModel's answers with the live run's latency. Postings marked HOT take four times as long,
    like the long postings whose reasoning ran past 3,000 tokens."""

    def __init__(self, scale: float, seed: int) -> None:
        self.inner = FakeModel(latency=0, seed=seed)
        self.scale = scale
        self.rng = random.Random(seed)
        self.calls = 0

    async def complete(self, model: str, messages: list[dict], think: bool = True) -> str:
        self.calls += 1
        seconds = min(MAX, self.rng.lognormvariate(MU, SIGMA))
        if HOT in messages[-1]["content"]:
            seconds *= 4
        await asyncio.sleep(seconds / self.scale)
        return await self.inner.complete(model, messages, think)


async def run(
    postings: list[tuple[str, str]],
    *,
    scale: float,
    shards: int = 1,
    workers: int = 8,
    seed: int = 7,
    engine: Engine | None = None,
) -> tuple[Engine, list[Job], float]:
    """Submit (company, text) pairs with one intake task per company, as batches do, and wait for all.
    Returns the engine (started; the caller shuts it down), the jobs, and the wall time in real seconds."""
    if engine is None:
        engine = Engine(
            LiveLikeModel(scale, seed),
            nano_model="fake-nano",
            ultra_model="fake-ultra",
            shards=shards,
            workers=workers,
            queue_capacity=32,
            model_concurrency=workers,
            log_interval=0.01,
        )
        await engine.start()
    by_company: dict[str, list[str]] = {}
    for company, text in postings:
        by_company.setdefault(company, []).append(text)
    jobs: list[Job] = []

    async def intake(company: str, texts: list[str]) -> None:
        for text in texts:
            jobs.append(await engine.submit(text, source=company, key=company))

    start = time.perf_counter()
    await asyncio.gather(*(intake(c, t) for c, t in by_company.items()))
    await asyncio.gather(*(job.wait() for job in jobs))
    return engine, jobs, (time.perf_counter() - start) * scale


def seconds(jobs: list[Job], scale: float) -> list[float]:
    """Each job's time from submission to verdict, in real seconds, sorted."""
    return sorted(job.ms_between(JobState.QUEUED, JobState.DONE) / 1000 * scale for job in jobs)


def pct(values: list[float], q: float) -> float:
    return values[max(0, math.ceil(q * len(values)) - 1)]


def median_of(results: list[tuple]) -> tuple:
    """Element-wise median across runs."""
    return tuple(statistics.median(column) for column in zip(*results))


def minutes(s: float) -> str:
    return f"{s / 60:.1f} min" if s >= 90 else f"{s:.0f} s"


def spread(postings: int, companies: int = 20) -> list[tuple[str, str]]:
    return [(f"company{i % companies}", text) for i, text in enumerate(numbered_postings(postings))]


async def workers_table(scale: float, seeds: list[int]) -> list[str]:
    rows = [
        "| Workers | Wall time for 200 postings | Postings per minute | Time to verdict p50 / p95 |",
        "| --- | --- | --- | --- |",
    ]
    for workers in (1, 2, 4, 8, 16):
        results = []
        for seed in seeds:
            engine, jobs, wall = await run(spread(200), scale=scale, workers=workers, seed=seed)
            await engine.shutdown()
            times = seconds(jobs, scale)
            results.append((wall, pct(times, 0.5), pct(times, 0.95)))
        wall, p50, p95 = median_of(results)
        rows.append(f"| {workers} | {minutes(wall)} | {200 / wall * 60:.0f} | {minutes(p50)} / {minutes(p95)} |")
        print(rows[-1], flush=True)
    return rows


async def cache_table(scale: float, seeds: list[int]) -> list[str]:
    # Ten copies of each of 20 postings, all submitted at once: single-flight makes one call per text.
    dupes = [(f"company{i % 20}", f"repeat {i % 20}\n{text}") for i, text in enumerate(numbered_postings(20) * 10)]
    results = []
    for seed in seeds:
        postings = spread(200)
        engine, _, cold = await run(postings, scale=scale, seed=seed)
        cold_calls = engine.model.inner.calls
        _, _, warm = await run(postings, scale=scale, engine=engine)
        warm_calls = engine.model.inner.calls - cold_calls
        _, _, burst = await run(dupes, scale=scale, engine=engine)
        burst_calls = engine.model.inner.calls - cold_calls - warm_calls
        coalesced = engine.metrics.counters["cache_coalesced"]
        await engine.shutdown()
        results.append((cold, cold_calls, warm, warm_calls, burst, burst_calls, coalesced))
        print(f"seed {seed}: {results[-1]}", flush=True)
    cold, cold_calls, warm, warm_calls, burst, burst_calls, coalesced = median_of(results)
    return [
        "| Run (8 workers) | Wall time | Model calls | Model cost at live prices |",
        "| --- | --- | --- | --- |",
        f"| 200 postings, cache cold | {minutes(cold)} | {cold_calls:.0f} | ${200 * LIVE_COST_PER_POSTING:.2f} |",
        # No model calls, so nothing to scale: this is the real time, mostly waiting on the log.
        f"| The same 200 again, cache warm | {warm / scale:.1f} s | {warm_calls:.0f} | $0.00 |",
        f"| 200 submissions of 20 distinct postings, all at once | {minutes(burst)} | {burst_calls:.0f} "
        f"| ${20 * LIVE_COST_PER_POSTING:.2f}; {coalesced:.0f} submissions waited on a call already in flight |",
    ]


async def shards_table(scale: float, seeds: list[int]) -> list[str]:
    """Even load (20 companies, 10 postings each), then the same with one company adding 60 long postings."""
    rows = [
        "| Load | Shards (8 workers in all) | Ordinary postings: time to verdict p50 / p95 | Wall time |",
        "| --- | --- | --- | --- |",
    ]
    hot = [("bigco", f"{text}\n{HOT}") for text in numbered_postings(260)[200:]]
    for load, extra in (("20 companies, 10 postings each", []), ("The same, plus one company with 60 long postings", hot)):
        for shards in (1, 4):
            results = []
            for seed in seeds:
                engine, jobs, wall = await run(extra + spread(200), scale=scale, shards=shards, seed=seed)
                await engine.shutdown()
                ordinary = seconds([j for j in jobs if j.source != "bigco"], scale)
                results.append((pct(ordinary, 0.5), pct(ordinary, 0.95), wall))
            p50, p95, wall = median_of(results)
            rows.append(f"| {load} | {shards} | {minutes(p50)} / {minutes(p95)} | {minutes(wall)} |")
            print(rows[-1], flush=True)
    return rows


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scale", type=float, default=100, help="how many times faster than real time")
    parser.add_argument("--runs", type=int, default=3, help="seeds per setting; the median is reported")
    args = parser.parse_args()

    seeds = list(range(7, 7 + args.runs))
    for title, table in (
        ("Workers (1 shard)", workers_table),
        ("Cache", cache_table),
        ("Shards", shards_table),
    ):
        print(f"\n## {title}\n", flush=True)
        rows = await table(args.scale, seeds)
        print("\n".join(rows), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
