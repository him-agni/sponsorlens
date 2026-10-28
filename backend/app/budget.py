"""Spending limits for the public demo: an end date, a dollar cap per UTC day and a request limit per hour."""

import time
from collections import deque
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta, timezone

from app.engine.metrics import Metrics


# Hackathon dates are Pacific time. December is all PST (UTC-8), so a fixed offset is exact and
# needs no time zone database, which Windows Python lacks.
PACIFIC = timezone(timedelta(hours=-8), "PST")


def demo_over(until: date | None, now: datetime | None = None) -> bool:
    """True once `until`, the last live day, has passed in Pacific time. None means no end date."""
    if until is None:
        return False
    return (now or datetime.now(UTC)).astimezone(PACIFIC).date() > until


class BudgetExceeded(Exception):
    """Raised in place of a model call once the day's budget is spent, or the demo has ended."""


class Budget:
    """Spend per UTC day, read from the cost counter the model client keeps.

    It lives in memory, so a restart starts the day's count again. Calls already in flight when the
    cap is reached still finish, so the day can overshoot by a few calls' worth.
    """

    def __init__(
        self,
        metrics: Metrics,
        daily_usd: float,
        today: Callable[[], date] | None = None,
        until: date | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.metrics = metrics
        self.until = until
        self._now = now or (lambda: datetime.now(UTC))
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
        # Also enforced here, not only in the API, so a batch still running at midnight stops too.
        if demo_over(self.until, self._now()):
            self.metrics.inc("budget_refusals")
            raise BudgetExceeded("the live demo has ended")
        if self.spent() >= self.limit:
            self.metrics.inc("budget_refusals")
            raise BudgetExceeded(f"today's ${self.limit / 1_000_000:.2f} demo budget is spent")


class HourlyLimit:
    """At most `per_hour` requests in any sliding hour, across all callers."""

    def __init__(self, per_hour: int, clock: Callable[[], float] = time.monotonic) -> None:
        self.per_hour = per_hour
        self._clock = clock
        self._times: deque[float] = deque()

    def take(self, count: int = 1) -> bool:
        """Count `count` requests. False, counting none, means the hour's allowance can't cover them."""
        now = self._clock()
        while self._times and now - self._times[0] >= 3600:
            self._times.popleft()
        if len(self._times) + count > self.per_hour:
            return False
        self._times.extend([now] * count)
        return True
