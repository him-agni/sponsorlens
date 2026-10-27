import asyncio
import time

from app.analyzer import PROMPT_VERSION, Analyzer
from app.engine.cache import AnalysisCache, cache_key, content_hash
from app.engine.guarded import GuardedModel
from app.engine.jobs import Job, JobState
from app.engine.log import GroupCommitLog, LogStore, MemoryLogStore
from app.engine.metrics import Metrics
from app.engine.pool import WorkerPool
from app.engine.queue import BoundedQueue
from app.engine.ring import HashRing
from app.llm import ChatModel
from app.normalize import normalize
from app.schemas import Analysis


class Shard:
    """One bounded queue and the workers that drain it."""

    def __init__(self, index: int, capacity: int, workers: int, handler, metrics: Metrics) -> None:
        self.index = index
        self.queue = BoundedQueue[Job](capacity)
        self.pool = WorkerPool(self.queue, handler, workers, metrics)


class Engine:
    """Jobs are routed by key (the company) over a consistent-hash ring to one of several shards.

    Each shard has its own bounded queue and workers, modelling one node of a multi-node design in a
    single process; every model call still goes through one GuardedModel, so the global concurrency
    cap holds across shards. Before any model call the cache is checked, and a job counts as done
    only once its record is on disk in the log. On start the log is replayed: the cache is refilled
    and finished jobs are remembered, so submitting one again returns its result with no model call.
    """

    def __init__(
        self,
        model: ChatModel,
        *,
        nano_model: str,
        ultra_model: str,
        shards: int = 4,
        workers: int = 8,
        queue_capacity: int = 32,
        model_concurrency: int = 8,
        retry_base_delay: float = 0.5,
        cache_capacity: int = 4096,
        log_store: LogStore | None = None,
        log_interval: float = 0.1,
        metrics: Metrics | None = None,
    ) -> None:
        self.metrics = metrics or Metrics()
        self.nano_model = nano_model
        self.ultra_model = ultra_model
        self.model = GuardedModel(model, self.metrics, concurrency=model_concurrency, base_delay=retry_base_delay)
        self.analyzer = Analyzer(self.model, nano_model, ultra_model)
        self.cache = AnalysisCache(cache_capacity, metrics=self.metrics)
        self.log_store = log_store or MemoryLogStore()
        self.log = GroupCommitLog(self.log_store, log_interval, self.metrics)
        self.ring = HashRing(shards)
        per_shard_workers = max(1, workers // shards)
        per_shard_capacity = max(1, queue_capacity // shards)
        self.shards = [Shard(i, per_shard_capacity, per_shard_workers, self._handle, self.metrics) for i in range(shards)]
        self.jobs: dict[str, Job] = {}
        self.recovered: dict[str, Analysis] = {}
        self.replayed: list[dict] = []
        self._register_gauges()

    def _register_gauges(self) -> None:
        gauge = self.metrics.gauge
        gauge("queue_depth", lambda: sum(len(s.queue) for s in self.shards))
        gauge("queue_capacity", lambda: sum(s.queue.capacity for s in self.shards))
        gauge("workers_busy", lambda: sum(s.pool.busy for s in self.shards))
        gauge("workers_total", lambda: sum(s.pool.size for s in self.shards))
        gauge("shards", lambda: len(self.shards))
        gauge("cache_size", lambda: len(self.cache))
        for s in self.shards:
            gauge(f"shard{s.index}_queue_depth", lambda s=s: len(s.queue))
            gauge(f"shard{s.index}_queue_peak", lambda s=s: s.queue.peak)
            gauge(f"shard{s.index}_workers_busy", lambda s=s: s.pool.busy)

    async def start(self) -> None:
        start = time.perf_counter()
        self.replayed = await self.log_store.replay()
        self.restore(self.replayed)
        self.metrics.gauge("recovery_records", lambda n=len(self.replayed): n)
        self.metrics.gauge("recovery_ms", lambda ms=round((time.perf_counter() - start) * 1000, 1): ms)
        self.log.start()
        for shard in self.shards:
            shard.pool.start(f"shard{shard.index}-worker")

    def restore(self, records: list[dict]) -> None:
        """Rebuild state from log records. Keyed by job ID and cache key, so replaying twice changes nothing."""
        for record in records:
            if record.get("type") == "done":
                analysis = Analysis.model_validate(record["analysis"])
                self.recovered[record["job_id"]] = analysis
                self.cache.put(record["cache_key"], analysis)

    def shard_for(self, key: str) -> int:
        return int(self.ring.shard_for(key))

    async def submit(
        self,
        text: str,
        source: str | None = None,
        *,
        key: str | None = None,
        job_id: str | None = None,
        batch_id: str | None = None,
    ) -> Job:
        """Queue a posting on its shard. Waits while that shard's queue is full; raises QueueClosed during shutdown.

        key picks the shard (a company, so one company's postings share a queue); it defaults to the
        job ID. A job ID already finished in the log comes back done at once, with no model call.
        """
        job = Job(text=text, source=source, batch_id=batch_id)
        if job_id:
            job.id = job_id
        job.shard = self.shard_for(key or job.id)
        self.jobs[job.id] = job
        if job.id in self.recovered:
            job.result = self.recovered[job.id]
            job.move(JobState.DONE)
            self.metrics.inc("jobs_recovered")
            return job
        try:
            await self.shards[job.shard].queue.put(job)
        except BaseException:
            del self.jobs[job.id]
            raise
        self.metrics.inc("jobs_submitted")
        return job

    async def analyze(self, text: str, source: str | None = None) -> Analysis:
        job = await (await self.submit(text, source)).wait()
        if job.state == JobState.FAILED:
            raise RuntimeError(job.error)
        return job.result

    async def shutdown(self, discard_pending: bool = False) -> list[Job]:
        """Stop intake, finish in-flight jobs, then flush the log. Discarded jobs are marked failed."""
        drained = await asyncio.gather(*(s.pool.drain(discard_pending) for s in self.shards))
        pending = [job for jobs in drained for job in jobs]
        for job in pending:
            job.error = "discarded at shutdown"
            job.move(JobState.FAILED)
        await self.log.close()
        return pending

    async def _handle(self, job: Job) -> Analysis:
        key = cache_key(content_hash(normalize(job.text)), PROMPT_VERSION, self.nano_model, self.ultra_model)
        analysis = await self.cache.get_or_compute(key, lambda: self._analyze(job.text))
        await self.log.append(
            {
                "type": "done",
                "job_id": job.id,
                "batch_id": job.batch_id,
                "source": job.source,
                "cache_key": key,
                "analysis": analysis.model_dump(mode="json"),
            }
        )
        return analysis

    async def _analyze(self, text: str) -> Analysis:
        self.metrics.inc("analyses")
        return await self.analyzer.analyze(text)
