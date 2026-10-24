import asyncio
import random

import httpx
import pytest
from openai import APIConnectionError

from app.engine.guarded import GuardedModel, backoff_delay, is_retryable
from app.engine.metrics import Metrics


class StatusError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


class FlakyModel:
    """Raises the given errors in order, then answers."""

    def __init__(self, *errors: Exception) -> None:
        self.errors = list(errors)
        self.calls = 0

    async def complete(self, model: str, messages: list[dict]) -> str:
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return "ok"


def guarded(inner, metrics: Metrics, sleeps: list[float], **kwargs) -> GuardedModel:
    async def record_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    return GuardedModel(inner, metrics, concurrency=2, rng=random.Random(0), sleep=record_sleep, **kwargs)


@pytest.mark.parametrize(
    ("error", "retryable"),
    [
        (StatusError(429), True),
        (StatusError(500), True),
        (StatusError(503), True),
        (StatusError(400), False),
        (StatusError(401), False),
        (APIConnectionError(request=httpx.Request("POST", "https://x")), True),
        (ValueError("bad json"), False),
    ],
)
def test_is_retryable(error: Exception, retryable: bool) -> None:
    assert is_retryable(error) is retryable


def test_backoff_grows_and_is_capped() -> None:
    rng = random.Random(1)
    for attempt in range(8):
        for _ in range(50):
            assert 0 <= backoff_delay(attempt, base=0.5, cap=8, rng=rng) <= min(8, 0.5 * 2**attempt)


async def test_429_then_success_is_retried_and_counted() -> None:
    metrics, sleeps = Metrics(), []
    inner = FlakyModel(StatusError(429), StatusError(503))
    assert await guarded(inner, metrics, sleeps).complete("m", []) == "ok"

    assert inner.calls == 3
    assert len(sleeps) == 2
    assert metrics.counters["retries"] == 2
    assert metrics.counters["rate_limited"] == 1
    assert metrics.counters["model_calls"] == 3


async def test_gives_up_after_three_tries() -> None:
    metrics, sleeps = Metrics(), []
    inner = FlakyModel(StatusError(500), StatusError(500), StatusError(500), StatusError(500))
    with pytest.raises(StatusError):
        await guarded(inner, metrics, sleeps).complete("m", [])
    assert inner.calls == 3
    assert metrics.counters["retries"] == 2


async def test_client_errors_are_not_retried() -> None:
    metrics, sleeps = Metrics(), []
    inner = FlakyModel(StatusError(400))
    with pytest.raises(StatusError):
        await guarded(inner, metrics, sleeps).complete("m", [])
    assert inner.calls == 1
    assert sleeps == []


async def test_concurrency_cap_holds() -> None:
    peak = in_flight = 0

    class SlowModel:
        async def complete(self, model: str, messages: list[dict]) -> str:
            nonlocal peak, in_flight
            in_flight += 1
            peak = max(peak, in_flight)
            await asyncio.sleep(0.01)
            in_flight -= 1
            return "ok"

    model = GuardedModel(SlowModel(), Metrics(), concurrency=3)
    await asyncio.gather(*(model.complete("m", []) for _ in range(20)))
    assert peak == 3
    assert model.in_flight == 0
