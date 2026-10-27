"""Record a sample run for the web app's sample mode, shown while the engine wakes or has no key.

Runs against a running API: analyzes the example postings, runs a batch while recording /metrics
once a second, then saves everything under web/public/sample/. Record from the live model for the
version that ships; a fake-model recording is marked as such in the file.

Run from backend/: uv run python -m scripts.record_sample [--api http://localhost:8000] [--per-company 10]
"""

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

from app.fixtures import load_fixtures

OUT = Path(__file__).resolve().parents[2] / "web" / "public" / "sample"
EXAMPLES = {
    "f09-hard-sponsorship-in-benefits": "Sponsorship listed under benefits",
    "f02-no-sponsorship": "No sponsorship, now or later",
    "f05-export-control": "Export control: U.S. persons only",
    "f11-hard-contradictory": "Offers sponsorship, then rules it out",
}
STATUSES = ["ead", "opt", "h1b", "green_card"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--per-company", type=int, default=10)
    args = parser.parse_args()
    api = httpx.Client(base_url=args.api, timeout=300)
    OUT.mkdir(parents=True, exist_ok=True)
    backend = api.get("/metrics").json()["backend"]
    recorded = time.strftime("%Y-%m-%d")

    fixtures = {f.id: f for f in load_fixtures()}
    examples = []
    for fixture_id, title in EXAMPLES.items():
        text = fixtures[fixture_id].posting
        print(f"Analyzing example: {title}")
        response = api.post("/api/analyze", json={"text": text, "status": "h1b"})
        response.raise_for_status()
        examples.append({"id": fixture_id, "title": title, "text": text, "response": response.json()})
    _save("examples.json", {"backend": backend, "recorded": recorded, "examples": examples})

    batch_id = api.post("/api/batch", json={"per_company": args.per_company, "status": "h1b"}).json()["id"]
    print(f"Batch {batch_id} started; recording /metrics once a second")
    timeline = []
    while True:
        timeline.append(api.get("/metrics").json())
        view = api.get(f"/api/batch/{batch_id}").json()
        progress = view["progress"]
        print(f"  {progress.get('done', 0)}/{progress['total']} done", flush=True)
        if view["finished"]:
            break
        time.sleep(1)
    timeline.append(api.get("/metrics").json())
    _save("metrics.json", {"backend": backend, "recorded": recorded, "snapshots": timeline})

    views = {status: api.get(f"/api/batch/{batch_id}", params={"status": status}).json() for status in STATUSES}
    _save("batch.json", {"backend": backend, "recorded": recorded, "views": views})
    print(f"Saved a {backend}-model sample to {OUT}")
    return 0


def _save(name: str, data: dict) -> None:
    (OUT / name).write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
