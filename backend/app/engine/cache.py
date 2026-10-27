import asyncio
import hashlib
import threading
from collections import OrderedDict
from collections.abc import Awaitable, Callable

from app.engine.metrics import Metrics
from app.schemas import Analysis


def content_hash(normalized_text: str) -> str:
    return hashlib.sha256(normalized_text.encode()).hexdigest()


def cache_key(content: str, prompt_version: str, nano_model: str, ultra_model: str) -> str:
    """The status is left out on purpose: signals don't depend on it, so switching status reuses them."""
    return hashlib.sha256(f"{prompt_version}|{nano_model}|{ultra_model}|{content}".encode()).hexdigest()


class _Shard:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.entries: OrderedDict[str, Analysis] = OrderedDict()
        self.in_flight: dict[str, asyncio.Future[Analysis]] = {}


class AnalysisCache:
    """An LRU cache split into shards by key, with single-flight per key.

    Single-flight: the first caller for a missing key computes it; callers that arrive while it is
    running wait for that result instead of making their own model call. The same job listed in
    several cities is the real case. A failure is passed to every waiter and is not cached.

    Each shard has its own lock. The critical sections never await, so under asyncio they are atomic
    anyway; the locks keep the cache correct if a threaded backend shares it (a stretch goal).
    """

    def __init__(self, capacity: int = 4096, shards: int = 8, metrics: Metrics | None = None) -> None:
        self.capacity_per_shard = max(1, capacity // shards)
        self.metrics = metrics or Metrics()
        self._shards = [_Shard() for _ in range(shards)]

    def __len__(self) -> int:
        return sum(len(shard.entries) for shard in self._shards)

    def _shard(self, key: str) -> _Shard:
        return self._shards[int(key[:8], 16) % len(self._shards)]

    def get(self, key: str) -> Analysis | None:
        shard = self._shard(key)
        with shard.lock:
            if key in shard.entries:
                shard.entries.move_to_end(key)
                return shard.entries[key]
        return None

    def put(self, key: str, value: Analysis) -> None:
        shard = self._shard(key)
        with shard.lock:
            shard.entries[key] = value
            shard.entries.move_to_end(key)
            while len(shard.entries) > self.capacity_per_shard:
                shard.entries.popitem(last=False)
                self.metrics.inc("cache_evictions")

    async def get_or_compute(self, key: str, compute: Callable[[], Awaitable[Analysis]]) -> Analysis:
        shard = self._shard(key)
        with shard.lock:
            if key in shard.entries:
                shard.entries.move_to_end(key)
                self.metrics.inc("cache_hits")
                return shard.entries[key]
            leader = shard.in_flight.get(key)
            if leader is None:
                future = shard.in_flight[key] = asyncio.get_running_loop().create_future()
        if leader is not None:
            self.metrics.inc("cache_coalesced")
            return await asyncio.shield(leader)

        self.metrics.inc("cache_misses")
        try:
            value = await compute()
        except BaseException as error:
            with shard.lock:
                del shard.in_flight[key]
            # Waiters get an ordinary exception even if the leader was cancelled, so they fail as jobs.
            future.set_exception(error if isinstance(error, Exception) else RuntimeError("computation cancelled"))
            future.exception()  # mark it retrieved when no one was waiting
            raise
        with shard.lock:
            del shard.in_flight[key]
        self.put(key, value)
        future.set_result(value)
        return value
