import asyncio
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4


class JobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


FINISHED = {JobState.DONE, JobState.FAILED}


@dataclass
class Job:
    """One posting moving through the engine: queued, running, then done or failed."""

    text: str
    source: str | None = None
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    state: JobState = JobState.QUEUED
    stamps: dict[JobState, float] = field(default_factory=dict)
    result: Any = None
    error: str | None = None
    _finished: asyncio.Event = field(default_factory=asyncio.Event, repr=False)

    def __post_init__(self) -> None:
        self.stamps[JobState.QUEUED] = time.time()

    def move(self, state: JobState) -> None:
        self.state = state
        self.stamps[state] = time.time()
        if state in FINISHED:
            self._finished.set()

    def ms_between(self, start: JobState, end: JobState) -> float | None:
        if start in self.stamps and end in self.stamps:
            return (self.stamps[end] - self.stamps[start]) * 1000
        return None

    async def wait(self) -> "Job":
        await self._finished.wait()
        return self

    def summary(self) -> dict:
        return {
            "id": self.id,
            "source": self.source,
            "state": self.state,
            "stamps": {state.value: stamp for state, stamp in self.stamps.items()},
            "error": self.error,
        }
