"""Run a batch through the engine on FakeModel and watch backpressure live. Costs nothing.

Run from backend/: uv run python -m scripts.rehearse [--jobs 200] [--rate-limit 0.05]
Phase 2 gate: queue depth reaches capacity, returns to zero, and every job finishes.
"""

import argparse
import asyncio
import sys
import time

from app.engine.engine import Engine
from app.engine.fake_model import FakeModel
from app.engine.jobs import FINISHED
from app.fixtures import load_fixtures


def bar(value: int, total: int, width: int = 20) -> str:
    filled = round(width * value / total) if total else 0
    return "#" * filled + "." * (width - filled)


def line(engine: Engine, elapsed: float) -> str:
    snap = engine.metrics.snapshot()
    gauges, counters = snap["gauges"], snap["counters"]
    p95 = snap["histograms"].get("model_latency_ms", {}).get("p95")
    return (
        f"{elapsed:5.1f}s  queue [{bar(gauges['queue_depth'], gauges['queue_capacity'])}] "
        f"{gauges['queue_depth']:>3}/{gauges['queue_capacity']}  "
        f"workers {gauges['workers_busy']}/{gauges['workers_total']}  "
        f"model {gauges['model_in_flight']}/{gauges['model_concurrency']}  "
        f"done {counters.get('jobs_done', 0):>4}  failed {counters.get('jobs_failed', 0)}  "
        f"retries {counters.get('retries', 0)}  p95 {p95 or 0:.0f} ms"
    )


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=int, default=200)
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
        workers=args.workers,
        queue_capacity=args.capacity,
        model_concurrency=args.concurrency,
    )
    postings = [f.posting for f in load_fixtures()]
    await engine.start()
    start = time.monotonic()

    async def produce() -> None:
        for i in range(args.jobs):
            await engine.submit(postings[i % len(postings)], source=f"rehearsal:{i}")

    producer = asyncio.create_task(produce())
    while not producer.done() or any(job.state not in FINISHED for job in engine.jobs.values()):
        print(line(engine, time.monotonic() - start), flush=True)
        await asyncio.sleep(0.5)
    print(line(engine, time.monotonic() - start))
    await engine.shutdown()

    counters = engine.metrics.counters
    reached_capacity = engine.queue.peak == engine.queue.capacity
    gate = reached_capacity and len(engine.queue) == 0 and counters["jobs_done"] + counters["jobs_failed"] == args.jobs
    print(f"\npeak queue depth {engine.queue.peak}/{engine.queue.capacity}, final depth {len(engine.queue)}")
    print(f"{counters['jobs_done']} done, {counters['jobs_failed']} failed, {counters['retries']} retries, "
          f"{counters['model_calls']} model calls, peak in-flight {model.peak_in_flight}/{args.concurrency}")
    print(f"Phase 2 gate (queue fills, drains to zero, every job finishes): {'PASS' if gate else 'FAIL'}")
    return 0 if gate else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
