from datetime import UTC, date, datetime

import pytest

from app.budget import Budget, BudgetExceeded, HourlyLimit, demo_over
from app.engine.metrics import Metrics


def test_budget_refuses_once_the_day_is_spent() -> None:
    metrics = Metrics()
    budget = Budget(metrics, daily_usd=0.01)
    metrics.inc("cost_micro_usd", 9_999)
    budget.check()
    metrics.inc("cost_micro_usd", 1)
    with pytest.raises(BudgetExceeded, match=r"\$0\.01"):
        budget.check()
    assert metrics.counters["budget_refusals"] == 1


def test_budget_starts_again_at_midnight_utc() -> None:
    metrics = Metrics()
    day = [date(2026, 10, 28)]
    budget = Budget(metrics, daily_usd=0.01, today=lambda: day[0])
    metrics.inc("cost_micro_usd", 10_000)
    with pytest.raises(BudgetExceeded):
        budget.check()

    day[0] = date(2026, 10, 29)
    budget.check()
    assert budget.spent() == 0
    metrics.inc("cost_micro_usd", 400)
    assert budget.spent() == 400


def test_budget_is_on_the_dashboard() -> None:
    metrics = Metrics()
    Budget(metrics, daily_usd=1.5)
    metrics.inc("cost_micro_usd", 250)
    gauges = metrics.snapshot()["gauges"]
    assert gauges["budget_spent_micro_usd"] == 250
    assert gauges["budget_limit_micro_usd"] == 1_500_000


def test_the_demo_ends_after_its_last_day_in_pacific_time() -> None:
    last = date(2026, 12, 15)
    # 11:59 pm PST on Dec 15 is 7:59 am UTC on Dec 16: still live.
    assert not demo_over(last, datetime(2026, 12, 16, 7, 59, tzinfo=UTC))
    assert demo_over(last, datetime(2026, 12, 16, 8, 0, tzinfo=UTC))
    assert not demo_over(None, datetime(2099, 1, 1, tzinfo=UTC))


def test_budget_refuses_every_call_once_the_demo_has_ended() -> None:
    metrics = Metrics()
    now = [datetime(2026, 12, 15, 20, 0, tzinfo=UTC)]
    budget = Budget(metrics, daily_usd=100, until=date(2026, 12, 15), now=lambda: now[0])
    budget.check()
    now[0] = datetime(2026, 12, 16, 9, 0, tzinfo=UTC)
    with pytest.raises(BudgetExceeded, match="ended"):
        budget.check()


def test_hourly_limit_takes_several_at_once_or_none() -> None:
    limit = HourlyLimit(per_hour=5, clock=lambda: 0.0)
    assert limit.take(3)
    assert not limit.take(3)
    assert limit.take(2)
    assert not limit.take()


def test_hourly_limit_slides() -> None:
    now = [0.0]
    limit = HourlyLimit(per_hour=2, clock=lambda: now[0])
    assert limit.take() and limit.take()
    assert not limit.take()
    now[0] = 3599.0
    assert not limit.take()
    now[0] = 3600.0
    assert limit.take()
