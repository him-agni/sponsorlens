import asyncio

from app.engine.engine import Engine
from app.engine.fake_model import FakeModel
from app.engine.jobs import JobState
from app.fixtures import load_fixtures

POSTINGS = [f.posting for f in load_fixtures()]


def engine(model: FakeModel, **kwargs) -> Engine:
    kwargs = {"workers": 8, "queue_capacity": 16, "model_concurrency": 4, "retry_base_delay": 0.001} | kwargs
    return Engine(model, nano_model="fake-nano", ultra_model="fake-ultra", **kwargs)


async def submit_all(e: Engine, count: int) -> list:
    return [await e.submit(POSTINGS[i % len(POSTINGS)], source=f"fake:{i}") for i in range(count)]


async def test_200_jobs_finish_without_deadlock() -> None:
    e = engine(FakeModel(latency=0.002, seed=1))
    await e.start()
    jobs = await asyncio.wait_for(submit_all(e, 200), timeout=10)
    await asyncio.wait_for(asyncio.gather(*(job.wait() for job in jobs)), timeout=10)
    await e.shutdown()

    assert all(job.state == JobState.DONE for job in jobs)
    counters = e.metrics.counters
    assert counters["jobs_submitted"] == counters["jobs_done"] == 200
    assert e.queue.peak == 16, "a producer faster than the workers fills the queue"
    assert len(e.queue) == 0


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
    e = engine(FakeModel(latency=0.05, jitter=0, seed=4), workers=4, model_concurrency=4)
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
    e = engine(FakeModel(latency=0, failure_rate=1.0, seed=7), workers=1)
    await e.start()
    jobs = await submit_all(e, 3)
    await asyncio.gather(*(job.wait() for job in jobs))
    await e.shutdown()
    assert [job.state for job in jobs] == [JobState.FAILED] * 3
    assert "FakeAPIError" in jobs[0].error
