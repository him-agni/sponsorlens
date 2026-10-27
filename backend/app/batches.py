"""Batches: fetch each company's board, push its postings through the engine, and resume after a restart.

One fetcher task per company. A fetcher submits its postings one at a time, so when that company's
shard queue is full the fetcher waits: that is the backpressure on intake.

The log holds a "batch" record, a "submitted" record per posting (source and title, never the
text) and a "batch_done" record. On restart, every batch without "batch_done" runs again from its
sources. The job ID is the batch ID plus the source, so a posting finished before the restart is
recognized by the engine and returned from the log with no model call.
"""

import asyncio
import time
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from uuid import uuid4

from app.engine.engine import Engine
from app.engine.jobs import Job, JobState
from app.greenhouse import Posting
from app.rules import decide
from app.schemas import Status

Fetch = Callable[[str], Awaitable[list[Posting]]]


@dataclass
class BatchItem:
    job_id: str
    source: str
    company: str
    title: str
    url: str
    location: str
    job: Job | None = None


@dataclass
class Batch:
    id: str
    companies: list[str]
    per_company: int
    status: Status
    created: float = field(default_factory=time.time)
    items: dict[str, BatchItem] = field(default_factory=dict)
    fetched: set[str] = field(default_factory=set)
    fetch_errors: dict[str, str] = field(default_factory=dict)
    finished: bool = False
    resumed: bool = False


class BatchRunner:
    def __init__(self, engine: Engine, fetch: Fetch) -> None:
        self.engine = engine
        self.fetch = fetch
        self.batches: dict[str, Batch] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    async def create(self, companies: list[str], per_company: int, status: Status) -> Batch:
        batch = Batch(id=uuid4().hex[:8], companies=companies, per_company=per_company, status=status)
        await self.engine.log.append(
            {
                "type": "batch",
                "batch_id": batch.id,
                "companies": companies,
                "per_company": per_company,
                "status": status.value,
            }
        )
        self.batches[batch.id] = batch
        self._launch(batch)
        return batch

    def resume(self, records: list[dict]) -> list[Batch]:
        """Rebuild batches from log records and restart every unfinished one."""
        for record in records:
            batch = self.batches.get(record.get("batch_id", ""))
            match record.get("type"):
                case "batch":
                    self.batches[record["batch_id"]] = Batch(
                        id=record["batch_id"],
                        companies=record["companies"],
                        per_company=record["per_company"],
                        status=Status(record["status"]),
                        created=record.get("ts", time.time()),
                    )
                case "submitted" if batch:
                    batch.items[record["job_id"]] = BatchItem(
                        **{k: record[k] for k in ("job_id", "source", "company", "title", "url", "location")}
                    )
                case "batch_done" if batch:
                    batch.finished = True
        unfinished = [batch for batch in self.batches.values() if not batch.finished]
        for batch in unfinished:
            batch.resumed = True
            self.engine.metrics.inc("batches_resumed")
            self._launch(batch)
        return unfinished

    async def wait(self, batch_id: str) -> None:
        if task := self._tasks.get(batch_id):
            await task

    async def stop(self) -> None:
        """Cancel running batches without marking them done, so they resume on the next start."""
        for task in self._tasks.values():
            task.cancel()
        await asyncio.gather(*self._tasks.values(), return_exceptions=True)

    def _launch(self, batch: Batch) -> None:
        self._tasks[batch.id] = asyncio.create_task(self._run(batch), name=f"batch-{batch.id}")

    async def _run(self, batch: Batch) -> None:
        await asyncio.gather(*(self._intake(batch, company) for company in batch.companies))
        await asyncio.gather(*(item.job.wait() for item in batch.items.values() if item.job))
        batch.finished = True
        await self.engine.log.append({"type": "batch_done", "batch_id": batch.id})
        self.engine.metrics.inc("batches_done")

    async def _intake(self, batch: Batch, company: str) -> None:
        start = time.perf_counter()
        try:
            postings = await self.fetch(company)
        except Exception as error:
            batch.fetch_errors[company] = f"{type(error).__name__}: {error}"
            self.engine.metrics.inc("fetch_errors")
            return
        self.engine.metrics.observe("fetch_ms", (time.perf_counter() - start) * 1000)
        batch.fetched.add(company)
        for posting in postings[: batch.per_company]:
            job_id = f"{batch.id}:{posting.source}"
            item = batch.items.get(job_id)
            if item is None:
                item = batch.items[job_id] = BatchItem(
                    job_id, posting.source, posting.company, posting.title, posting.url, posting.location
                )
                # Not awaited: losing this record in a crash is harmless, because resume re-fetches.
                self.engine.log.append({"type": "submitted", "batch_id": batch.id, **_fields(item)})
            item.job = await self.engine.submit(
                posting.text, source=posting.source, key=company, job_id=job_id, batch_id=batch.id
            )

    def view(self, batch: Batch, status: Status | None = None) -> dict:
        """Progress and results, with each verdict worked out for the given status."""
        status = status or batch.status
        rows = []
        for item in batch.items.values():
            job = item.job
            analysis = job.result if job and job.state == JobState.DONE else self.engine.recovered.get(item.job_id)
            state = job.state.value if job else ("done" if analysis else "unavailable")
            verdict = decide(analysis, status) if analysis else None
            rows.append(
                {
                    **_fields(item),
                    "shard": job.shard if job else None,
                    "state": state,
                    "error": job.error if job else None,
                    "company_name": analysis.company if analysis else None,
                    "verdict": verdict.model_dump(mode="json") if verdict else None,
                }
            )
        return {
            "id": batch.id,
            "status": status,
            "companies": batch.companies,
            "per_company": batch.per_company,
            "created": batch.created,
            "finished": batch.finished,
            "resumed": batch.resumed,
            "fetched": sorted(batch.fetched),
            "fetch_errors": batch.fetch_errors,
            "progress": {"total": len(rows), **Counter(row["state"] for row in rows)},
            "verdicts": dict(Counter(row["verdict"]["label"] for row in rows if row["verdict"])),
            "items": rows,
        }


def _fields(item: BatchItem) -> dict:
    return {
        "job_id": item.job_id,
        "source": item.source,
        "company": item.company,
        "title": item.title,
        "url": item.url,
        "location": item.location,
    }
