"""Phase 3 gate: kill the server mid-batch, restart it, and check that the batch finishes without
sending any finished job to the model again. Real Greenhouse postings, FakeModel, so it costs nothing.

Run from backend/: uv run python -m scripts.kill_test [--kill-at 80] [--port 8765]
"""

import argparse
import json
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

import httpx

BACKEND = Path(__file__).resolve().parents[1]
LOG = BACKEND / "data" / "kill-test.jsonl"


def start_server(port: int, latency: float) -> subprocess.Popen:
    env = os.environ | {"MODEL_BACKEND": "fake", "FAKE_LATENCY": str(latency), "LOG_PATH": str(LOG)}
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port), "--log-level", "warning"],
        cwd=BACKEND,
        env=env,
    )
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            if httpx.get(f"http://127.0.0.1:{port}/health").status_code == 200:
                return server
        except httpx.TransportError:
            time.sleep(0.2)
    server.kill()
    raise SystemExit("the server did not start")


def progress(view: dict) -> str:
    p = view["progress"]
    return f"{p.get('done', 0):>3} done, {p.get('running', 0)} running, {p.get('queued', 0):>3} queued of {p['total']}"


def done_records() -> Counter:
    lines = LOG.read_text(encoding="utf-8").splitlines() if LOG.exists() else []
    records = []
    for line in lines:
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return Counter(r["job_id"] for r in records if r.get("type") == "done")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kill-at", type=int, default=80, help="kill once this many postings are done")
    parser.add_argument("--per-company", type=int, default=10)
    parser.add_argument("--latency", type=float, default=0.3, help="seconds per fake model call")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    api = f"http://127.0.0.1:{args.port}"
    LOG.unlink(missing_ok=True)

    print("Starting the server on FakeModel and a fresh log...")
    server = start_server(args.port, args.latency)
    batch_id = httpx.post(f"{api}/api/batch", json={"per_company": args.per_company}, timeout=30).json()["id"]
    print(f"Batch {batch_id}: fetching the preset Greenhouse boards")
    while True:
        view = httpx.get(f"{api}/api/batch/{batch_id}").json()
        print(f"  {progress(view)}", flush=True)
        if view["progress"].get("done", 0) >= args.kill_at:
            break
        time.sleep(0.5)

    server.kill()
    server.wait()
    finished_before = done_records()
    print(f"\nKilled the server. The log holds {sum(finished_before.values())} finished postings.\n")

    print("Restarting: the log is replayed and the batch resumes from its sources...")
    restart = time.monotonic()
    server = start_server(args.port, args.latency)
    try:
        metrics = httpx.get(f"{api}/metrics").json()
        print(f"  replayed {metrics['gauges']['recovery_records']} records in {metrics['gauges']['recovery_ms']} ms")
        while not (view := httpx.get(f"{api}/api/batch/{batch_id}").json())["finished"]:
            print(f"  {progress(view)}", flush=True)
            time.sleep(0.5)
        print(f"  {progress(view)}  (resumed in {time.monotonic() - restart:.1f}s)")
        counters = httpx.get(f"{api}/metrics").json()["counters"]
    finally:
        server.kill()
        server.wait()

    finished_after = done_records()
    total = view["progress"]["total"]
    repeated = [job for job, count in finished_after.items() if count > 1]
    recovered = counters.get("jobs_recovered", 0)
    print(f"\n{total} postings; {view['progress'].get('done', 0)} done, {view['progress'].get('failed', 0)} failed")
    print(f"After the restart: {recovered} returned from the log, {counters.get('analyses', 0)} analyses, "
          f"{counters.get('model_calls', 0)} model calls, {counters.get('cache_hits', 0)} cache hits")
    print(f"Postings finished twice: {len(repeated)}")

    gate = (
        view["finished"]
        and view["progress"].get("done", 0) == total
        and not repeated
        and recovered == len(finished_before)
        and len(finished_after) == total
    )
    print(f"Phase 3 gate (survives a kill, no finished job sent again): {'PASS' if gate else 'FAIL'}")
    return 0 if gate else 1


if __name__ == "__main__":
    sys.exit(main())
