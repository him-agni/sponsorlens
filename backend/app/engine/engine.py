from app.analyzer import Analyzer
from app.engine.guarded import GuardedModel
from app.engine.jobs import Job, JobState
from app.engine.metrics import Metrics
from app.engine.pool import WorkerPool
from app.engine.queue import BoundedQueue
from app.llm import ChatModel
from app.schemas import Analysis


class Engine:
    """One bounded queue feeding a worker pool, with every model call going through GuardedModel.

    Phase 3 splits the queue into shards and adds the cache and the log in front of the model.
    """

    def __init__(
        self,
        model: ChatModel,
        *,
        nano_model: str,
        ultra_model: str,
        workers: int = 8,
        queue_capacity: int = 32,
        model_concurrency: int = 8,
        retry_base_delay: float = 0.5,
        metrics: Metrics | None = None,
    ) -> None:
        self.metrics = metrics or Metrics()
        self.model = GuardedModel(model, self.metrics, concurrency=model_concurrency, base_delay=retry_base_delay)
        self.analyzer = Analyzer(self.model, nano_model, ultra_model)
        self.queue = BoundedQueue[Job](queue_capacity)
        self.pool = WorkerPool(self.queue, self._handle, workers, self.metrics)
        self.jobs: dict[str, Job] = {}
        self.metrics.gauge("queue_depth", lambda: len(self.queue))
        self.metrics.gauge("queue_capacity", lambda: self.queue.capacity)
        self.metrics.gauge("queue_depth_peak", lambda: self.queue.peak)

    async def start(self) -> None:
        self.pool.start()

    async def submit(self, text: str, source: str | None = None) -> Job:
        """Queue a posting. Waits while the queue is full; raises QueueClosed during shutdown."""
        job = Job(text=text, source=source)
        self.jobs[job.id] = job
        try:
            await self.queue.put(job)
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
        """Stop intake and finish in-flight jobs. Discarded jobs are marked failed so no caller waits forever."""
        pending = await self.pool.drain(discard_pending)
        for job in pending:
            job.error = "discarded at shutdown"
            job.move(JobState.FAILED)
        return pending

    async def _handle(self, job: Job) -> Analysis:
        return await self.analyzer.analyze(job.text)
