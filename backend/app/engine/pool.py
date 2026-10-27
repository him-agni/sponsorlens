import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from app.engine.jobs import Job, JobState
from app.engine.metrics import Metrics
from app.engine.queue import BoundedQueue, QueueClosed

Handler = Callable[[Job], Awaitable[Any]]


class WorkerPool:
    """N worker tasks taking jobs from one queue. A failing job is marked failed; the worker carries on."""

    def __init__(self, queue: BoundedQueue[Job], handler: Handler, workers: int, metrics: Metrics) -> None:
        self.queue = queue
        self.handler = handler
        self.size = workers
        self.busy = 0
        self.metrics = metrics
        self._tasks: list[asyncio.Task] = []

    def start(self, name: str = "worker") -> None:
        self._tasks = [asyncio.create_task(self._work(), name=f"{name}-{i}") for i in range(self.size)]

    async def drain(self, discard_pending: bool = False) -> list[Job]:
        """Stop intake and wait for the workers to finish their jobs and exit.

        By default the workers also finish everything still queued. With discard_pending, queued jobs
        are taken off the queue and returned instead, so only in-flight jobs are finished.
        """
        pending = await self.queue.close(discard_pending)
        await asyncio.gather(*self._tasks)
        return pending

    async def _work(self) -> None:
        while True:
            try:
                job = await self.queue.get()
            except QueueClosed:
                return
            self.busy += 1
            job.move(JobState.RUNNING)
            try:
                job.result = await self.handler(job)
                job.move(JobState.DONE)
                self.metrics.inc("jobs_done")
            except Exception as error:
                job.error = f"{type(error).__name__}: {error}"
                job.move(JobState.FAILED)
                self.metrics.inc("jobs_failed")
            finally:
                self.busy -= 1
                self.metrics.observe("job_wait_ms", job.ms_between(JobState.QUEUED, JobState.RUNNING))
                self.metrics.observe("job_run_ms", job.ms_between(JobState.RUNNING, job.state))
