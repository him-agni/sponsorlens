import asyncio

import pytest

from app.engine.cache import AnalysisCache, cache_key
from app.schemas import Analysis


def analysis(company: str) -> Analysis:
    return Analysis(company=company, signals=[], nano_model="n", ultra_model="u", prompt_version="p")


def key(i: int) -> str:
    return cache_key(f"posting {i}", "p1", "nano", "ultra")


def test_the_key_depends_on_prompt_version_and_models() -> None:
    assert cache_key("x", "p1", "nano", "ultra") != cache_key("x", "p2", "nano", "ultra")
    assert cache_key("x", "p1", "nano", "ultra") != cache_key("x", "p1", "nano", "other")


def test_least_recently_used_entries_are_evicted() -> None:
    cache = AnalysisCache(capacity=2, shards=1)
    cache.put(key(1), analysis("a"))
    cache.put(key(2), analysis("b"))
    cache.get(key(1))
    cache.put(key(3), analysis("c"))
    assert cache.get(key(2)) is None
    assert cache.get(key(1)) is not None and cache.get(key(3)) is not None
    assert cache.metrics.counters["cache_evictions"] == 1


async def test_ten_identical_concurrent_jobs_make_one_model_call() -> None:
    cache = AnalysisCache()
    calls = 0

    async def compute() -> Analysis:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return analysis("acme")

    results = await asyncio.gather(*(cache.get_or_compute(key(1), compute) for _ in range(10)))
    assert calls == 1
    assert all(r.company == "acme" for r in results)
    counters = cache.metrics.counters
    assert counters["cache_misses"] == 1 and counters["cache_coalesced"] == 9

    await cache.get_or_compute(key(1), compute)
    assert calls == 1 and counters["cache_hits"] == 1


async def test_a_failure_reaches_every_waiter_and_is_not_cached() -> None:
    cache = AnalysisCache()
    calls = 0

    async def failing() -> Analysis:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        raise ValueError("model down")

    results = await asyncio.gather(*(cache.get_or_compute(key(1), failing) for _ in range(5)), return_exceptions=True)
    assert calls == 1
    assert all(isinstance(r, ValueError) for r in results)

    async def working() -> Analysis:
        return analysis("acme")

    assert (await cache.get_or_compute(key(1), working)).company == "acme"


async def test_a_cancelled_leader_fails_its_waiters_with_an_ordinary_error() -> None:
    cache = AnalysisCache()
    started = asyncio.Event()

    async def slow() -> Analysis:
        started.set()
        await asyncio.sleep(10)
        return analysis("never")

    leader = asyncio.create_task(cache.get_or_compute(key(1), slow))
    await started.wait()
    waiter = asyncio.create_task(cache.get_or_compute(key(1), slow))
    await asyncio.sleep(0)
    leader.cancel()
    with pytest.raises(RuntimeError, match="cancelled"):
        await waiter
