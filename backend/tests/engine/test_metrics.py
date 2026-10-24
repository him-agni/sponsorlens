from app.engine.metrics import Histogram, Metrics


def test_percentiles_use_nearest_rank() -> None:
    histogram = Histogram()
    for value in range(1, 101):
        histogram.observe(value)
    assert histogram.summary() == {"count": 100, "p50": 50, "p95": 95, "max": 100}


def test_histogram_keeps_a_recent_window_but_counts_everything() -> None:
    histogram = Histogram(window=10)
    for value in range(100):
        histogram.observe(value)
    summary = histogram.summary()
    assert summary["count"] == 100
    assert summary["p50"] == 94


def test_empty_histogram() -> None:
    assert Histogram().summary() == {"count": 0, "p50": None, "p95": None, "max": None}


def test_snapshot_reads_gauges_live() -> None:
    metrics = Metrics()
    depth = [3]
    metrics.gauge("queue_depth", lambda: depth[0])
    metrics.inc("jobs_done")
    metrics.inc("jobs_done", 2)
    metrics.observe("model_latency_ms", 12.34)

    assert metrics.snapshot()["gauges"] == {"queue_depth": 3}
    depth[0] = 0
    snapshot = metrics.snapshot()
    assert snapshot["gauges"] == {"queue_depth": 0}
    assert snapshot["counters"] == {"jobs_done": 3}
    assert snapshot["histograms"]["model_latency_ms"]["p50"] == 12.3
