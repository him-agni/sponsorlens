"""Score the Nemotron cascade in LangSmith: the 27 invented postings as a dataset, each setup as an experiment.

Run from backend/: uv run python -m scripts.experiment [--setup cascade nano-only] [--concurrency 3]
Each run uploads the dataset if it changed, then runs every chosen setup over it. LangSmith keeps
each experiment with its traces (every Nemotron call, its prompt, reply and tokens) and puts the
setups side by side for comparison. About $0.01 to $0.08 of Nebius credit per setup.

Each setup's latest results are also saved to backend/results/<setup>.json, and
docs/accuracy-by-posting.md is rebuilt from those files, so the results are kept in the repo too.

Local only: it sends the invented test postings, never anything a visitor pastes. The hosted app
does not import LangSmith, and Render installs without the dev dependencies.
"""

import argparse
import asyncio
import json
import os
import statistics
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from langsmith import Client, aevaluate
from langsmith.wrappers import wrap_openai

from app.analyzer import PROMPT_VERSION, Analyzer
from app.config import REPO_ROOT, settings
from app.engine.metrics import Metrics
from app.fixtures import Fixture, load_fixtures, load_hard_cases
from app.llm import ChatModel, TokenFactoryModel, make_client
from app.rules import decide
from app.schemas import Status

DATASET = "sponsorlens-postings"
RESULTS = REPO_ROOT / "backend" / "results"
REPORT = REPO_ROOT / "docs" / "accuracy-by-posting.md"


@dataclass(frozen=True)
class Setup:
    description: str
    find_model: str
    classify_model: str
    think: bool = True


NANO, ULTRA = settings.nano_model, settings.ultra_model
SETUPS = {
    "cascade": Setup("Nano finds the sentences, Ultra classifies them (what the app runs)", NANO, ULTRA),
    "nano-only": Setup("Nano for both steps", NANO, NANO),
    "ultra-only": Setup("Ultra for both steps", ULTRA, ULTRA),
    "cascade-no-reasoning": Setup("The cascade with reasoning off", NANO, ULTRA, think=False),
}


class WithoutReasoning:
    """Asks every question with reasoning off, to measure what reasoning buys."""

    def __init__(self, model: ChatModel) -> None:
        self.model = model

    async def complete(self, model: str, messages: list[dict], think: bool = True) -> str:
        return await self.model.complete(model, messages, think=False)


def example(case: Fixture) -> dict:
    return {
        "inputs": {"posting": case.posting},
        "outputs": {
            "verdicts": {status.value: label.value for status, label in case.expected.items()},
            "signals": sorted(s.value for s in case.signals),
        },
        "metadata": {"id": case.id, "note": case.note, "set": "hard" if case.id.startswith("h") else "core"},
    }


def sync_dataset(client: Client) -> None:
    """Create the dataset, or bring it up to date with the fixture files. Each change is a new dataset version."""
    if client.has_dataset(dataset_name=DATASET):
        dataset = client.read_dataset(dataset_name=DATASET)
    else:
        dataset = client.create_dataset(DATASET, description="Invented US job postings with the expected verdict for each status")
    stored = {e.metadata.get("id"): e for e in client.list_examples(dataset_id=dataset.id)}
    added = []
    for case in load_fixtures() + load_hard_cases():
        wanted = example(case)
        if case.id not in stored:
            added.append(wanted)
        elif (stored[case.id].inputs, stored[case.id].outputs) != (wanted["inputs"], wanted["outputs"]):
            client.update_example(stored[case.id].id, inputs=wanted["inputs"], outputs=wanted["outputs"], metadata=wanted["metadata"])
    if added:
        client.create_examples(dataset_id=dataset.id, examples=added)
    print(f"Dataset {DATASET}: {len(stored) + len(added)} postings ({len(added)} added)")


def target_for(setup: Setup):
    # Wrapped once, so every Nemotron call shows up in the trace with its prompt, reply and tokens.
    client = wrap_openai(make_client(max_retries=0), chat_name="Nemotron")

    async def check_posting(inputs: dict) -> dict:
        # Each posting gets its own counters, so its cost is exact even with postings running in parallel.
        metrics = Metrics()
        model: ChatModel = TokenFactoryModel(client, metrics=metrics)
        if not setup.think:
            model = WithoutReasoning(model)
        analysis = await Analyzer(model, setup.find_model, setup.classify_model).analyze(inputs["posting"])
        return {
            "verdicts": {status.value: decide(analysis, status).label.value for status in Status},
            "signals": sorted({s.type.value for s in analysis.signals}),
            "quotes": [s.quote for s in analysis.signals],
            "unverified_quotes": analysis.unverified_quotes,
            "cost_usd": metrics.counters["cost_micro_usd"] / 1_000_000,
        }

    return check_posting


# Evaluators. A posting whose run failed has no outputs, and scores zero on all of them.


def all_statuses_right(outputs: dict, reference_outputs: dict) -> bool:
    return (outputs or {}).get("verdicts") == reference_outputs["verdicts"]


def statuses_right(outputs: dict, reference_outputs: dict) -> float:
    got = (outputs or {}).get("verdicts") or {}
    want = reference_outputs["verdicts"]
    return sum(got.get(status) == label for status, label in want.items()) / len(want)


def quotes_verified(outputs: dict) -> bool:
    """Every quote the model gave was found word for word in the posting."""
    return bool(outputs) and outputs["unverified_quotes"] == 0


def signals_match(outputs: dict, reference_outputs: dict) -> bool:
    return (outputs or {}).get("signals") == reference_outputs["signals"]


def cost_usd(outputs: dict) -> dict:
    return {"key": "cost_usd", "score": (outputs or {}).get("cost_usd", 0.0)}


EVALUATORS = [all_statuses_right, statuses_right, quotes_verified, signals_match, cost_usd]


async def run(name: str, setup: Setup, client: Client, concurrency: int) -> None:
    results = await aevaluate(
        target_for(setup),
        data=DATASET,
        evaluators=EVALUATORS,
        experiment_prefix=name,
        description=setup.description,
        metadata={
            "setup": name,
            "prompt_version": PROMPT_VERSION,
            "find_model": setup.find_model,
            "classify_model": setup.classify_model,
            "reasoning": setup.think,
        },
        max_concurrency=concurrency,
        client=client,
    )
    record = summarize(name, setup, results.experiment_name, [row async for row in results])
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"{name}.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    total = record["summary"]
    print(
        f"{name}: {total['all_statuses_right']}/{total['postings']} postings right for all four statuses, "
        f"{total['quotes_verified']}/{total['postings']} with every quote verified, "
        f"${total['cost_usd']:.3f} in all ({results.experiment_name})"
    )


def summarize(name: str, setup: Setup, experiment: str, rows: list[dict]) -> dict:
    """One setup's run as plain data: a summary, then each posting's expected and actual answers."""
    postings = []
    for row in rows:
        run, example = row["run"], row["example"]
        got = run.outputs or {}
        scores = {r.key: r.score for r in row["evaluation_results"]["results"]}
        postings.append(
            {
                "id": example.metadata["id"],
                "set": example.metadata["set"],
                "all_statuses_right": bool(scores.get("all_statuses_right")),
                "expected": example.outputs["verdicts"],
                "got": got.get("verdicts"),
                "signals_expected": example.outputs["signals"],
                "signals_found": got.get("signals"),
                "quotes": got.get("quotes"),
                "unverified_quotes": got.get("unverified_quotes"),
                "cost_usd": got.get("cost_usd"),
                "seconds": round((run.end_time - run.start_time).total_seconds(), 1) if run.end_time else None,
                "error": run.error,
            }
        )
    postings.sort(key=lambda p: p["id"])
    seconds = sorted(p["seconds"] for p in postings if p["seconds"] is not None)
    return {
        "setup": name,
        "description": setup.description,
        "date": date.today().isoformat(),
        "experiment": experiment,
        "prompt_version": PROMPT_VERSION,
        "find_model": setup.find_model,
        "classify_model": setup.classify_model,
        "reasoning": setup.think,
        "summary": {
            "postings": len(postings),
            "all_statuses_right": sum(p["all_statuses_right"] for p in postings),
            "quotes_verified": sum(p["unverified_quotes"] == 0 for p in postings),
            "signals_match": sum(p["signals_found"] == p["signals_expected"] for p in postings),
            "cost_usd": round(sum(p["cost_usd"] or 0 for p in postings), 4),
            "median_seconds": statistics.median(seconds) if seconds else None,
            "slowest_seconds": seconds[-1] if seconds else None,
        },
        "postings": postings,
    }


def write_report() -> None:
    """Rebuild docs/accuracy-by-posting.md from every saved setup in backend/results/."""
    records = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(RESULTS.glob("*.json"))]
    records.sort(key=lambda r: list(SETUPS).index(r["setup"]) if r["setup"] in SETUPS else len(SETUPS))
    lines = [
        "# Accuracy by posting",
        "",
        "Generated by `backend/scripts/experiment.py` from `backend/results/`; do not edit by hand. "
        "The postings are in `backend/fixtures/`, and the findings are in [accuracy.md](accuracy.md).",
        "",
        "## Setups",
        "",
        "| Setup | Run | All four statuses right | Every quote verified | Signals match | Cost | Median, slowest |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in records:
        s = r["summary"]
        lines.append(
            f"| `{r['setup']}`: {r['description']} | {r['date']}, prompt {r['prompt_version']} "
            f"| {s['all_statuses_right']}/{s['postings']} | {s['quotes_verified']}/{s['postings']} "
            f"| {s['signals_match']}/{s['postings']} | ${s['cost_usd']:.3f} "
            f"| {s['median_seconds']} s, {s['slowest_seconds']} s |"
        )
    lines += [
        "",
        "## Each posting",
        "",
        "A check mark means all four verdicts were right. Otherwise the cell lists each wrong status as got → expected.",
        "",
        "| Posting | " + " | ".join(f"`{r['setup']}`" for r in records) + " |",
        "|---|" + "---|" * len(records),
    ]
    ids = sorted({p["id"] for r in records for p in r["postings"]})
    by_setup = [{p["id"]: p for p in r["postings"]} for r in records]
    for posting_id in ids:
        cells = [_cell(postings.get(posting_id)) for postings in by_setup]
        lines.append(f"| {posting_id} | " + " | ".join(cells) + " |")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _cell(posting: dict | None) -> str:
    if posting is None:
        return ""
    if posting["error"] or posting["got"] is None:
        return "error"
    if posting["all_statuses_right"]:
        return "✓"
    wrong = [f"{status}: {posting['got'].get(status)} → {want}" for status, want in posting["expected"].items() if posting["got"].get(status) != want]
    return "<br>".join(wrong)


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--setup", nargs="+", choices=SETUPS, default=["cascade"])
    parser.add_argument("--concurrency", type=int, default=3)
    args = parser.parse_args()

    if not settings.nebius_api_key or not settings.langsmith_api_key:
        print("Set NEBIUS_API_KEY and LANGSMITH_API_KEY in .env first.")
        return 2
    # The SDK reads its key from the environment; this is a local process, so nothing else sees it.
    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    client = Client()
    sync_dataset(client)
    for name in args.setup:
        await run(name, SETUPS[name], client, args.concurrency)
    write_report()
    print(f"Saved results to {RESULTS} and {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
