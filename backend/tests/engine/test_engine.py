import asyncio

from app.engine.engine import Engine
from app.engine.fake_model import FakeModel
from app.engine.jobs import JobState
from app.engine.log import MemoryLogStore
from app.fixtures import load_fixtures, numbered_postings

POSTINGS = numbered_postings(200)


def engine(model: FakeModel, **kwargs) -> Engine:
    kwargs = {
        "shards": 4,
        "workers": 8,
        "queue_capacity": 16,
        "model_concurrency": 4,
        "retry_base_delay": 0.001,
        "log_interval": 0.001,
    } | kwargs
    return Engine(model, nano_model="fake-nano", ultra_model="fake-ultra", **kwargs)


async def submit_all(e: Engine, count: int, batch_id: str | None = None) -> list:
    return [await e.submit(POSTINGS[i], source=f"fake:{i}", batch_id=batch_id) for i in range(count)]


async def test_200_jobs_finish_without_deadlock() -> None:
    e = engine(FakeModel(latency=0.002, seed=1))
    await e.start()
    jobs = await asyncio.wait_for(submit_all(e, 200), timeout=10)
    await asyncio.wait_for(asyncio.gather(*(job.wait() for job in jobs)), timeout=10)
    await e.shutdown()

    assert all(job.state == JobState.DONE for job in jobs)
    counters = e.metrics.counters
    assert counters["jobs_submitted"] == counters["jobs_done"] == 200
    assert any(s.queue.peak == s.queue.capacity == 4 for s in e.shards), "a fast producer fills a shard queue"
    assert all(len(s.queue) == 0 for s in e.shards)


async def test_jobs_with_the_same_key_share_a_shard() -> None:
    e = engine(FakeModel(latency=0.001, seed=8))
    await e.start()
    jobs = [await e.submit(POSTINGS[i], key="stripe") for i in range(10)]
    await asyncio.gather(*(job.wait() for job in jobs))
    await e.shutdown()
    assert len({job.shard for job in jobs}) == 1


async def test_in_flight_model_calls_never_exceed_the_cap() -> None:
    model = FakeModel(latency=0.005, seed=2)
    e = engine(model, workers=12, model_concurrency=3)
    await e.start()
    jobs = await submit_all(e, 60)
    await asyncio.gather(*(job.wait() for job in jobs))
    await e.shutdown()
    assert model.peak_in_flight == 3


async def test_injected_429s_and_503s_recover_through_retries() -> None:
    model = FakeModel(latency=0.001, rate_limit_rate=0.15, failure_rate=0.05, seed=3)
    e = engine(model)
    await e.start()
    jobs = await submit_all(e, 100)
    await asyncio.gather(*(job.wait() for job in jobs))
    await e.shutdown()

    counters = e.metrics.counters
    assert counters["retries"] > 0
    assert counters["rate_limited"] > 0
    done = sum(job.state == JobState.DONE for job in jobs)
    assert done == counters["jobs_done"]
    assert done >= 97, "with 3 tries, a job fails only if one call fails three times in a row"


async def test_drain_finishes_in_flight_jobs() -> None:
    e = engine(FakeModel(latency=0.05, jitter=0, seed=4), shards=1, workers=4, model_concurrency=4)
    await e.start()
    jobs = await submit_all(e, 12)
    await asyncio.sleep(0.02)
    running = [job for job in jobs if job.state == JobState.RUNNING]
    assert running, "some jobs should be mid-call when drain starts"

    discarded = await asyncio.wait_for(e.shutdown(discard_pending=True), timeout=5)
    assert all(job.state == JobState.DONE for job in running)
    assert all(job.state == JobState.FAILED and job.error == "discarded at shutdown" for job in discarded)
    assert len(running) + len(discarded) == 12


async def test_drain_by_default_finishes_the_backlog_too() -> None:
    e = engine(FakeModel(latency=0.002, seed=5))
    await e.start()
    jobs = await submit_all(e, 30)
    assert await e.shutdown() == []
    assert all(job.state == JobState.DONE for job in jobs)


async def test_job_lifecycle_stamps_are_in_order() -> None:
    e = engine(FakeModel(latency=0.002, seed=6))
    await e.start()
    job = await (await e.submit(POSTINGS[0])).wait()
    await e.shutdown()
    stamps = job.stamps
    assert stamps[JobState.QUEUED] <= stamps[JobState.RUNNING] <= stamps[JobState.DONE]
    assert e.metrics.histograms["job_run_ms"].count == 1


async def test_a_failing_job_does_not_stop_its_worker() -> None:
    e = engine(FakeModel(latency=0, failure_rate=1.0, seed=7), shards=1, workers=1)
    await e.start()
    jobs = await submit_all(e, 3)
    await asyncio.gather(*(job.wait() for job in jobs))
    await e.shutdown()
    assert [job.state for job in jobs] == [JobState.FAILED] * 3
    assert "FakeAPIError" in jobs[0].error


async def test_a_repeated_posting_is_analyzed_once() -> None:
    e = engine(FakeModel(latency=0.002, seed=9))
    await e.start()
    posting = load_fixtures()[0].posting
    jobs = [await e.submit(posting, source=f"city:{i}") for i in range(10)]
    await asyncio.gather(*(job.wait() for job in jobs))
    await e.shutdown()
    assert e.metrics.counters["analyses"] == 1
    assert all(job.result == jobs[0].result for job in jobs)


async def test_every_done_batch_job_has_a_record_in_the_log() -> None:
    store = MemoryLogStore()
    e = engine(FakeModel(latency=0.001, seed=10), log_store=store)
    await e.start()
    jobs = await submit_all(e, 20, batch_id="b1")
    await asyncio.gather(*(job.wait() for job in jobs))
    await e.shutdown()
    logged = {r["job_id"] for r in store.records if r["type"] == "done"}
    assert logged == {job.id for job in jobs}
    assert all("text" not in r for r in store.records), "posting text is never stored"


async def test_a_single_check_leaves_nothing_behind() -> None:
    """Pasted postings are someone's own: nothing on disk, and the text is dropped once answered."""
    store = MemoryLogStore()
    e = engine(FakeModel(latency=0.001, seed=15), log_store=store)
    await e.start()
    job = await (await e.submit(POSTINGS[0], source="pasted")).wait()
    await e.shutdown()
    assert job.result is not None
    assert [r for r in store.records if r["type"] == "done"] == []
    assert job.text == ""


async def test_a_restarted_engine_skips_finished_jobs() -> None:
    store = MemoryLogStore()
    first = engine(FakeModel(latency=0.001, seed=11), log_store=store)
    await first.start()
    done = [await first.submit(POSTINGS[i], job_id=f"job-{i}", batch_id="b1") for i in range(10)]
    await asyncio.gather(*(job.wait() for job in done))
    await first.shutdown()

    second = engine(FakeModel(latency=0.001, seed=12), log_store=store)
    await second.start()
    jobs = [await second.submit(POSTINGS[i], job_id=f"job-{i}", batch_id="b1") for i in range(15)]
    await asyncio.gather(*(job.wait() for job in jobs))
    await second.shutdown()

    counters = second.metrics.counters
    assert counters["jobs_recovered"] == 10
    assert counters["analyses"] == 5, "only the five new jobs reach the model"
    assert [job.result for job in jobs[:10]] == [job.result for job in done]
    assert second.metrics.snapshot()["gauges"]["recovery_records"] == 10


async def test_replaying_the_log_twice_gives_the_same_state() -> None:
    store = MemoryLogStore()
    e = engine(FakeModel(latency=0.001, seed=13), log_store=store)
    await e.start()
    jobs = await submit_all(e, 10, batch_id="b1")
    await asyncio.gather(*(job.wait() for job in jobs))
    await e.shutdown()

    restored = engine(FakeModel(seed=14))
    restored.restore(store.records)
    once = (dict(restored.recovered), len(restored.cache))
    restored.restore(store.records)
    assert (dict(restored.recovered), len(restored.cache)) == once
    assert len(restored.cache) == 10
