"""Every model call in the engine goes through GuardedModel: a global concurrency cap, retries and metrics."""

import asyncio
import random
import time
from collections.abc import Awaitable, Callable

from openai import APIConnectionError

from app.engine.metrics import Metrics
from app.llm import ChatModel


def is_retryable(error: BaseException) -> bool:
    """Rate limits (429), server errors (5xx) and dropped connections are worth another try."""
    if isinstance(error, APIConnectionError):
        return True
    status = getattr(error, "status_code", None)
    return status == 429 or (isinstance(status, int) and status >= 500)


def backoff_delay(attempt: int, base: float, cap: float, rng: random.Random) -> float:
    """Full jitter: a random wait between 0 and base * 2^attempt, capped, so retries spread out."""
    return rng.uniform(0, min(cap, base * 2**attempt))


class GuardedModel:
    def __init__(
        self,
        inner: ChatModel,
        metrics: Metrics,
        *,
        concurrency: int,
        attempts: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 8.0,
        rng: random.Random | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.inner = inner
        self.metrics = metrics
        self.concurrency = concurrency
        self.attempts = attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.in_flight = 0
        self._slots = asyncio.Semaphore(concurrency)
        self._rng = rng or random.Random()
        self._sleep = sleep
        metrics.gauge("model_in_flight", lambda: self.in_flight)
        metrics.gauge("model_concurrency", lambda: self.concurrency)

    async def complete(self, model: str, messages: list[dict]) -> str:
        for attempt in range(self.attempts):
            # The slot is held only during the call, never during the backoff sleep.
            async with self._slots:
                self.in_flight += 1
                self.metrics.inc("model_calls")
                start = time.perf_counter()
                try:
                    return await self.inner.complete(model, messages)
                except Exception as error:
                    self.metrics.inc("model_errors")
                    if getattr(error, "status_code", None) == 429:
                        self.metrics.inc("rate_limited")
                    if not is_retryable(error) or attempt == self.attempts - 1:
                        raise
                finally:
                    self.in_flight -= 1
                    self.metrics.observe("model_latency_ms", (time.perf_counter() - start) * 1000)
            self.metrics.inc("retries")
            await self._sleep(backoff_delay(attempt, self.base_delay, self.max_delay, self._rng))
        raise AssertionError("unreachable")
