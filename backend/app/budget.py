"""Spending limits for the public demo: a dollar cap per UTC day and a request limit per hour."""

import time
from collections import deque
from collections.abc import Callable
from datetime import UTC, date, datetime

from app.engine.metrics import Metrics


class BudgetExceeded(Exception):
    """Raised in place of a model call once the day's budget is spent."""


class Budget:
    """Spend per UTC day, read from the cost counter the model client keeps.

    It lives in memory, so a restart starts the day's count again. Calls already in flight when the
    cap is reached still finish, so the day can overshoot by a few calls' worth.
    """

    def __init__(self, metrics: Metrics, daily_usd: float, today: Callable[[], date] | None = None) -> None:
        self.metrics = metrics
        self.limit = round(daily_usd * 1_000_000)
        self._today = today or (lambda: datetime.now(UTC).date())
        self._day = self._today()
        self._start = 0
        metrics.gauge("budget_spent_micro_usd", self.spent)
        metrics.gauge("budget_limit_micro_usd", lambda: self.limit)

    def spent(self) -> int:
        """Millionths of a dollar spent since midnight UTC, or since the process started."""
        total = self.metrics.counters["cost_micro_usd"]
        if (day := self._today()) != self._day:
            self._day, self._start = day, total
        return total - self._start

    def check(self) -> None:
        if self.spent() >= self.limit:
            self.metrics.inc("budget_refusals")
            raise BudgetExceeded(f"today's ${self.limit / 1_000_000:.2f} demo budget is spent")


class HourlyLimit:
    """At most `per_hour` requests in any sliding hour, across all callers."""

    def __init__(self, per_hour: int, clock: Callable[[], float] = time.monotonic) -> None:
        self.per_hour = per_hour
        self._clock = clock
        self._times: deque[float] = deque()

    def take(self) -> bool:
        """Count one request. False means the hour's allowance is used up."""
        now = self._clock()
        while self._times and now - self._times[0] >= 3600:
            self._times.popleft()
        if len(self._times) >= self.per_hour:
            return False
        self._times.append(now)
        return True
