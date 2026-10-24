import math
import time
from collections import defaultdict, deque
from collections.abc import Callable


class Histogram:
    """Keeps the most recent samples, so percentiles follow current behavior rather than all history."""

    def __init__(self, window: int = 2048) -> None:
        self.count = 0
        self._samples: deque[float] = deque(maxlen=window)

    def observe(self, value: float) -> None:
        self.count += 1
        self._samples.append(value)

    def summary(self) -> dict:
        ordered = sorted(self._samples)
        return {
            "count": self.count,
            "p50": _percentile(ordered, 0.50),
            "p95": _percentile(ordered, 0.95),
            "max": round(ordered[-1], 1) if ordered else None,
        }


def _percentile(ordered: list[float], q: float) -> float | None:
    """Nearest-rank percentile of an already sorted list."""
    if not ordered:
        return None
    return round(ordered[max(0, math.ceil(q * len(ordered)) - 1)], 1)


class Metrics:
    """Counters, live gauges and latency histograms. GET /metrics returns snapshot()."""

    def __init__(self) -> None:
        self.started = time.monotonic()
        self.counters: defaultdict[str, int] = defaultdict(int)
        self.histograms: defaultdict[str, Histogram] = defaultdict(Histogram)
        self._gauges: dict[str, Callable[[], float]] = {}

    def inc(self, name: str, amount: int = 1) -> None:
        self.counters[name] += amount

    def observe(self, name: str, value: float) -> None:
        self.histograms[name].observe(value)

    def gauge(self, name: str, read: Callable[[], float]) -> None:
        """Register a gauge that is read when a snapshot is taken, so it can never go stale."""
        self._gauges[name] = read

    def snapshot(self) -> dict:
        return {
            "uptime_s": round(time.monotonic() - self.started, 1),
            "counters": dict(self.counters),
            "gauges": {name: read() for name, read in self._gauges.items()},
            "histograms": {name: h.summary() for name, h in self.histograms.items()},
        }
