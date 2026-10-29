import asyncio
from collections import Counter

from app import batches
from app.batches import BatchRunner
from app.engine.engine import Engine
from app.engine.fake_model import FakeModel
from app.engine.log import MemoryLogStore
from app.fixtures import load_fixtures
from app.postings import Posting
from app.schemas import Status

FIXTURES = load_fixtures()


def postings_for(company: str, count: int = 6) -> list[Posting]:
    return [
        Posting(
            source=f"fake:{company}:{i}",
            company=company.title(),
            title=f"Engineer {i}",
            url=f"https://example.com/{company}/{i}",
            location="Austin, TX",
            text=f"{FIXTURES[i % len(FIXTURES)].posting}\nRole {company} {i}.",
        )
        for i in range(count)
    ]


async def fetch(company: str) -> list[Posting]:
    if company == "broken":
        raise ConnectionError("board unavailable")
    return postings_for(company)


def engine(store: MemoryLogStore, seed: int = 1) -> Engine:
    return Engine(
        FakeModel(latency=0.002, seed=seed),
        nano_model="fake-nano",
        ultra_model="fake-ultra",
        shards=4,
        workers=8,
        queue_capacity=8,
        retry_base_delay=0.001,
        log_interval=0.001,
        log_store=store,
    )


async def run_batch(store: MemoryLogStore, companies: list[str], per_company: int = 5) -> tuple[Engine, BatchRunner, str]:
    e = engine(store)
    await e.start()
    runner = BatchRunner(e, fetch)
    batch = await runner.create(companies, per_company, Status.OPT)
    await asyncio.wait_for(runner.wait(batch.id), timeout=10)
    await e.shutdown()
    return e, runner, batch.id


async def test_a_batch_runs_every_company_to_the_end() -> None:
    store = MemoryLogStore()
    e, runner, batch_id = await run_batch(store, ["acme", "globex", "initech"])
    view = runner.view(runner.batches[batch_id])

    assert view["finished"]
    assert view["progress"] == {"total": 15, "done": 15}
    assert sum(view["verdicts"].values()) == 15
    assert {r["type"] for r in store.records} == {"batch", "submitted", "done", "batch_done"}


async def test_one_company_shares_one_shard() -> None:
    _, runner, batch_id = await run_batch(MemoryLogStore(), ["acme", "globex"])
    shards = {(row["company"], row["shard"]) for row in runner.view(runner.batches[batch_id])["items"]}
    assert len(shards) == 2


async def test_a_failing_board_is_reported_and_the_rest_continue() -> None:
    _, runner, batch_id = await run_batch(MemoryLogStore(), ["acme", "broken"])
    view = runner.view(runner.batches[batch_id])
    assert view["finished"]
    assert view["progress"]["done"] == 5
    assert "board unavailable" in view["fetch_errors"]["broken"]


async def test_the_view_follows_the_status() -> None:
    _, runner, batch_id = await run_batch(MemoryLogStore(), ["acme"])
    batch = runner.batches[batch_id]
    opt = runner.view(batch, Status.OPT)["verdicts"]
    green_card = runner.view(batch, Status.GREEN_CARD)["verdicts"]
    assert opt != green_card, "the same signals give different verdicts for different statuses"


async def test_a_batch_cut_off_mid_run_resumes_without_repeating_finished_jobs() -> None:
    full = MemoryLogStore()
    await run_batch(full, ["acme", "globex", "initech"])

    # The log as a crash would leave it: no batch_done, and only the first 6 jobs written as done.
    done_records = [r for r in full.records if r["type"] == "done"]
    survived = {r["job_id"] for r in done_records[:6]}
    crashed = MemoryLogStore()
    crashed.records = [
        r for r in full.records if r["type"] in ("batch", "submitted") or r.get("job_id") in survived and r["type"] == "done"
    ]

    e = engine(crashed, seed=2)
    await e.start()
    runner = BatchRunner(e, fetch)
    [batch] = runner.resume(e.replayed)
    await asyncio.wait_for(runner.wait(batch.id), timeout=10)
    await e.shutdown()

    assert runner.view(batch)["progress"] == {"total": 15, "done": 15}
    assert e.metrics.counters["jobs_recovered"] == 6
    assert e.metrics.counters["analyses"] == 9, "only the 9 unfinished jobs reach the model"
    done_per_job = Counter(r["job_id"] for r in crashed.records if r["type"] == "done")
    assert set(done_per_job.values()) == {1}, "no job is done twice"
    assert any(r["type"] == "batch_done" for r in crashed.records)


async def test_a_finished_batch_is_not_resumed() -> None:
    store = MemoryLogStore()
    await run_batch(store, ["acme"])
    e = engine(store)
    await e.start()
    runner = BatchRunner(e, fetch)
    assert runner.resume(e.replayed) == []
    [batch] = runner.batches.values()
    assert runner.view(batch)["progress"] == {"total": 5, "done": 5}
    await e.shutdown()


async def test_only_the_newest_batches_are_kept(monkeypatch) -> None:
    monkeypatch.setattr(batches, "MAX_BATCHES", 2)
    e = engine(MemoryLogStore())
    await e.start()
    runner = BatchRunner(e, fetch)
    ids = []
    for _ in range(3):
        batch = await runner.create(["acme"], 1, Status.OPT)
        await asyncio.wait_for(runner.wait(batch.id), timeout=10)
        ids.append(batch.id)
    await e.shutdown()
    assert list(runner.batches) == ids[1:]
