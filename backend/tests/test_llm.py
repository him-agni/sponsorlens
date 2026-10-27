from app.engine.metrics import Metrics
from app.llm import TokenFactoryModel


def test_usage_is_counted_and_priced() -> None:
    metrics = Metrics()
    model = TokenFactoryModel(client=object(), metrics=metrics)
    model.record_usage("nvidia/Nemotron-3-Ultra-550b-a55b", 1_000, 2_000)
    model.record_usage("unknown/model", 500, 500)

    assert metrics.counters["tokens_in"] == 1_500
    assert metrics.counters["tokens_out"] == 2_500
    # Ultra: 1,000 in at $1/M plus 2,000 out at $3/M is $0.007; the unknown model costs nothing.
    assert metrics.counters["cost_micro_usd"] == 7_000
