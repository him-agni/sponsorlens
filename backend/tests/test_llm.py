import pytest

from app.budget import Budget, BudgetExceeded
from app.engine.metrics import Metrics
from app.llm import TokenFactoryModel


async def test_a_spent_budget_stops_the_call_before_it_is_made() -> None:
    metrics = Metrics()
    # No client: reaching the API would fail with AttributeError, not BudgetExceeded.
    model = TokenFactoryModel(client=object(), metrics=metrics, budget=Budget(metrics, daily_usd=0.001))
    model.record_usage("nvidia/Nemotron-3-Ultra-550b-a55b", 1_000, 0)
    with pytest.raises(BudgetExceeded):
        await model.complete("nvidia/Nemotron-3-Ultra-550b-a55b", [])


def test_usage_is_counted_and_priced() -> None:
    metrics = Metrics()
    model = TokenFactoryModel(client=object(), metrics=metrics)
    model.record_usage("nvidia/Nemotron-3-Ultra-550b-a55b", 1_000, 2_000)
    model.record_usage("unknown/model", 500, 500)

    assert metrics.counters["tokens_in"] == 1_500
    assert metrics.counters["tokens_out"] == 2_500
    # Ultra: 1,000 in at $1/M plus 2,000 out at $3/M is $0.007; the unknown model costs nothing.
    assert metrics.counters["cost_micro_usd"] == 7_000
