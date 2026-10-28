from types import SimpleNamespace

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


class FakeCompletions:
    """Stands in for the OpenAI SDK's chat.completions, recording each request."""

    def __init__(self, content: str | None = '{"ok": true}') -> None:
        self.requests: list[dict] = []
        self.content = content

    async def create(self, **request):
        self.requests.append(request)
        message = SimpleNamespace(content=self.content)
        usage = SimpleNamespace(prompt_tokens=1_000, completion_tokens=2_000)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)


def client_with(completions: FakeCompletions):
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


async def test_a_call_asks_for_json_at_temperature_zero_and_records_its_cost() -> None:
    metrics = Metrics()
    completions = FakeCompletions()
    model = TokenFactoryModel(client=client_with(completions), metrics=metrics)
    assert await model.complete("nvidia/Nemotron-3-Ultra-550b-a55b", [{"role": "user", "content": "hi"}]) == '{"ok": true}'

    request = completions.requests[0]
    assert request["response_format"] == {"type": "json_object"}
    assert request["temperature"] == 0
    assert request["max_tokens"] == 8192
    assert request["extra_body"] is None, "reasoning stays on by default"
    assert metrics.counters["cost_micro_usd"] == 7_000


async def test_reasoning_can_be_turned_off_for_a_retry() -> None:
    metrics = Metrics()
    completions = FakeCompletions()
    model = TokenFactoryModel(client=client_with(completions), metrics=metrics)
    await model.complete("nano", [], think=False)
    assert completions.requests[0]["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}
    assert metrics.counters["calls_without_reasoning"] == 1


async def test_an_empty_reply_is_an_empty_string() -> None:
    model = TokenFactoryModel(client=client_with(FakeCompletions(content=None)))
    assert await model.complete("nano", []) == ""
