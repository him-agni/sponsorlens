import asyncio
import json
import os
import time
from pathlib import Path
from typing import Protocol

from app.engine.metrics import Metrics


class LogStore(Protocol):
    """Where log records live. append_batch returns once the records are durable."""

    async def append_batch(self, records: list[dict]) -> None: ...

    async def replay(self) -> list[dict]: ...


class MemoryLogStore:
    """Keeps records in a list. For tests, and for runs that don't need to survive a restart."""

    def __init__(self) -> None:
        self.records: list[dict] = []

    async def append_batch(self, records: list[dict]) -> None:
        self.records.extend(records)

    async def replay(self) -> list[dict]:
        return list(self.records)


class JsonlLogStore:
    """An append-only file of JSON lines, fsynced on every batch.

    A crash during a write can leave a half-written last line. replay skips it and cuts it off, so
    the next append starts on a clean line instead of gluing onto the fragment.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.skipped = 0

    async def append_batch(self, records: list[dict]) -> None:
        await asyncio.to_thread(self._write, records)

    async def replay(self) -> list[dict]:
        return await asyncio.to_thread(self._read)

    def _write(self, records: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = "".join(json.dumps(record, separators=(",", ":")) + "\n" for record in records)
        with open(self.path, "a", encoding="utf-8") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())

    def _read(self) -> list[dict]:
        if not self.path.exists():
            return []
        records = []
        good_end = 0
        with open(self.path, "rb") as file:
            for line in file:
                if not line.endswith(b"\n"):
                    self.skipped += 1  # the half-written tail; cut off below
                    break
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    self.skipped += 1
                good_end = file.tell()
        if good_end < self.path.stat().st_size:
            with open(self.path, "r+b") as file:
                file.truncate(good_end)
        return records


class GroupCommitLog:
    """A single writer task in front of a LogStore.

    append() buffers a record and returns a future. The writer waits about one interval so more
    records can join, then makes one append_batch call (one write and one fsync) for the whole
    buffer and resolves every future. Awaiting the future means the record is on disk, which is
    what lets a job count as done only once its record is durable.
    """

    def __init__(self, store: LogStore, interval: float = 0.1, metrics: Metrics | None = None) -> None:
        self.store = store
        self.interval = interval
        self.metrics = metrics or Metrics()
        self._buffer: list[tuple[dict, asyncio.Future[None]]] = []
        self._wake = asyncio.Event()
        self._closed = False
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="log-writer")

    def append(self, record: dict) -> asyncio.Future[None]:
        if self._closed:
            raise RuntimeError("the log is closed")
        future = asyncio.get_running_loop().create_future()
        self._buffer.append(({"ts": round(time.time(), 3), **record}, future))
        self._wake.set()
        return future

    async def close(self) -> None:
        """Flush what is buffered, then stop the writer."""
        self._closed = True
        self._wake.set()
        if self._task:
            await self._task

    async def _run(self) -> None:
        batch: list[tuple[dict, asyncio.Future[None]]] = []
        try:
            while True:
                await self._wake.wait()
                if not self._closed:
                    await asyncio.sleep(self.interval)
                self._wake.clear()
                batch, self._buffer = self._buffer, []
                if batch:
                    await self._flush(batch)
                if self._closed and not self._buffer:
                    return
        except asyncio.CancelledError:
            # Whether or not a write was mid-flight, none of these records was confirmed durable.
            self._fail(batch + self._buffer, RuntimeError("the log writer stopped"))
            raise

    async def _flush(self, batch: list[tuple[dict, asyncio.Future[None]]]) -> None:
        start = time.perf_counter()
        try:
            await self.store.append_batch([record for record, _ in batch])
        except Exception as error:
            self.metrics.inc("log_errors")
            self._fail(batch, error)
            return
        for _, future in batch:
            if not future.done():
                future.set_result(None)
        self.metrics.inc("log_flushes")
        self.metrics.inc("log_records", len(batch))
        self.metrics.observe("log_flush_ms", (time.perf_counter() - start) * 1000)
        self.metrics.observe("log_batch_size", len(batch))

    @staticmethod
    def _fail(batch: list[tuple[dict, asyncio.Future[None]]], error: Exception) -> None:
        for _, future in batch:
            if not future.done():
                future.set_exception(error)
                future.exception()  # mark it retrieved for records no one awaits
