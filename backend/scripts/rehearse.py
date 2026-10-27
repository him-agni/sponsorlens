"""Run a batch through the engine on FakeModel and watch backpressure live. Costs nothing.

Run from backend/: uv run python -m scripts.rehearse [--jobs 200] [--rate-limit 0.05]
Phase 2 gate: a shard's queue reaches capacity, every queue returns to zero, and every job finishes.
"""

import argparse
import asyncio
import sys
import time

from app.engine.engine import Engine
from app.engine.fake_model import FakeModel
from app.engine.jobs import FINISHED
from app.fixtures import numbered_postings


def bar(value: int, total: int, width: int = 20) -> str:
    filled = round(width * value / total) if total else 0
    return "#" * filled + "." * (width - filled)


def line(engine: Engine, elapsed: float) -> str:
    snap = engine.metrics.snapshot()
    gauges, counters = snap["gauges"], snap["counters"]
    p95 = snap["histograms"].get("model_latency_ms", {}).get("p95")
    shards = " ".join(f"{gauges[f'shard{i}_queue_depth']:>2}" for i in range(gauges["shards"]))
    return (
        f"{elapsed:5.1f}s  queue [{bar(gauges['queue_depth'], gauges['queue_capacity'])}] "
        f"{gauges['queue_depth']:>3}/{gauges['queue_capacity']} (shards {shards})  "
        f"workers {gauges['workers_busy']}/{gauges['workers_total']}  "
        f"model {gauges['model_in_flight']}/{gauges['model_concurrency']}  "
        f"done {counters.get('jobs_done', 0):>4}  failed {counters.get('jobs_failed', 0)}  "
        f"retries {counters.get('retries', 0)}  p95 {p95 or 0:.0f} ms"
    )


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=int, default=200)
    parser.add_argument("--shards", type=int, default=4)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--capacity", type=int, default=32)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--latency", type=float, default=0.3, help="seconds per fake model call")
    parser.add_argument("--rate-limit", type=float, default=0.05, help="share of calls that get a 429")
    parser.add_argument("--failure", type=float, default=0.01, help="share of calls that get a 503")
    args = parser.parse_args()

    model = FakeModel(latency=args.latency, rate_limit_rate=args.rate_limit, failure_rate=args.failure, seed=42)
    engine = Engine(
        model,
        nano_model="fake-nano",
        ultra_model="fake-ultra",
        shards=args.shards,
        workers=args.workers,
        queue_capacity=args.capacity,
        model_concurrency=args.concurrency,
    )
    postings = numbered_postings(args.jobs)
    await engine.start()
    start = time.monotonic()

    async def produce() -> None:
        for i, posting in enumerate(postings):
            await engine.submit(posting, source=f"rehearsal:{i}")

    producer = asyncio.create_task(produce())
    while not producer.done() or any(job.state not in FINISHED for job in engine.jobs.values()):
        print(line(engine, time.monotonic() - start), flush=True)
        await asyncio.sleep(0.5)
    print(line(engine, time.monotonic() - start))
    await engine.shutdown()

    counters = engine.metrics.counters
    reached_capacity = any(s.queue.peak == s.queue.capacity for s in engine.shards)
    drained = all(len(s.queue) == 0 for s in engine.shards)
    gate = reached_capacity and drained and counters["jobs_done"] + counters["jobs_failed"] == args.jobs
    peaks = ", ".join(f"{s.queue.peak}/{s.queue.capacity}" for s in engine.shards)
    print(f"\npeak depth per shard {peaks}; all drained: {drained}")
    print(f"{counters['jobs_done']} done, {counters['jobs_failed']} failed, {counters['retries']} retries, "
          f"{counters['model_calls']} model calls, peak in-flight {model.peak_in_flight}/{args.concurrency}")
    print(f"Phase 2 gate (a shard queue fills, all drain to zero, every job finishes): {'PASS' if gate else 'FAIL'}")
    return 0 if gate else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
