"""The 15 invented postings used by the eval, the tests and FakeModel rehearsals."""

import json
from functools import cache
from pathlib import Path

from pydantic import BaseModel

from app.schemas import Label, SignalType, Status

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "postings.json"


class Fixture(BaseModel):
    id: str
    note: str
    signals: list[SignalType]
    expected: dict[Status, Label]
    text: list[str]

    @property
    def posting(self) -> str:
        return "\n".join(self.text)


@cache
def load_fixtures() -> tuple[Fixture, ...]:
    return tuple(Fixture.model_validate(f) for f in json.loads(FIXTURES.read_text(encoding="utf-8")))


def numbered_postings(count: int) -> list[str]:
    """The fixtures repeated, each copy numbered so its text is unique and misses the cache."""
    postings = [f.posting for f in load_fixtures()]
    return [f"{postings[i % len(postings)]}\nPosting number {i + 1}." for i in range(count)]
