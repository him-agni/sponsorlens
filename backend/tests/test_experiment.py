import json
from datetime import datetime, timedelta
from types import SimpleNamespace

from app.fixtures import load_hard_cases
from scripts import experiment
from scripts.experiment import SETUPS, all_statuses_right, example, quotes_verified, signals_match, statuses_right, summarize

CASE = load_hard_cases()[0]
WANT = example(CASE)["outputs"]


def test_an_example_holds_the_posting_and_plain_expected_values() -> None:
    made = example(CASE)
    assert made["inputs"] == {"posting": CASE.posting}
    assert WANT == {
        "verdicts": {"ead": "blocked", "opt": "blocked", "h1b": "blocked", "green_card": "blocked"},
        "signals": ["security_clearance"],
    }
    assert made["metadata"]["set"] == "hard"


def test_a_right_answer_scores_full_marks() -> None:
    got = {**WANT, "unverified_quotes": 0}
    assert all_statuses_right(got, WANT) and signals_match(got, WANT) and quotes_verified(got)
    assert statuses_right(got, WANT) == 1


def test_one_wrong_status_costs_a_quarter() -> None:
    got = {**WANT, "verdicts": {**WANT["verdicts"], "green_card": "clear"}, "unverified_quotes": 1}
    assert not all_statuses_right(got, WANT)
    assert statuses_right(got, WANT) == 0.75
    assert not quotes_verified(got)


def test_a_failed_run_scores_zero() -> None:
    assert not all_statuses_right(None, WANT)
    assert statuses_right(None, WANT) == 0
    assert not quotes_verified(None)
    assert not signals_match(None, WANT)


def row(got: dict | None, seconds: float = 2.0, error: str | None = None) -> dict:
    """One result row as aevaluate yields it: the run, the dataset example and the evaluator scores."""
    start = datetime(2026, 10, 28, 12)
    made = example(CASE)
    run = SimpleNamespace(outputs=got, start_time=start, end_time=start + timedelta(seconds=seconds), error=error)
    stored = SimpleNamespace(outputs=made["outputs"], metadata=made["metadata"])
    scores = [SimpleNamespace(key="all_statuses_right", score=all_statuses_right(got, WANT))]
    return {"run": run, "example": stored, "evaluation_results": {"results": scores}}


def test_a_run_is_saved_with_its_summary_and_each_posting() -> None:
    right = {**WANT, "quotes": ["Active Top Secret/SCI clearance with polygraph."], "unverified_quotes": 0, "cost_usd": 0.002}
    record = summarize("cascade", SETUPS["cascade"], "cascade-1234", [row(right, 3.0), row(None, 9.0, "TimeoutError")])

    assert record["summary"] == {
        "postings": 2,
        "all_statuses_right": 1,
        "quotes_verified": 1,
        "signals_match": 1,
        "cost_usd": 0.002,
        "median_seconds": 6.0,
        "slowest_seconds": 9.0,
    }
    assert record["postings"][0]["quotes"] == right["quotes"]
    assert record["postings"][1]["error"] == "TimeoutError"


def test_the_report_marks_right_postings_and_spells_out_wrong_ones(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(experiment, "RESULTS", tmp_path)
    monkeypatch.setattr(experiment, "REPORT", tmp_path / "report.md")
    right = {**WANT, "unverified_quotes": 0, "cost_usd": 0.002}
    wrong = {**right, "verdicts": {**WANT["verdicts"], "green_card": "clear"}}
    for name, got in [("cascade", right), ("nano-only", wrong)]:
        record = summarize(name, SETUPS[name], name, [row(got)])
        (tmp_path / f"{name}.json").write_text(json.dumps(record), encoding="utf-8")

    experiment.write_report()
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert f"| {CASE.id} | ✓ | green_card: clear → blocked |" in report
