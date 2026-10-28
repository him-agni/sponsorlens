"""A stand-in for Token Factory, so tests and rehearsals cost nothing.

Latency, server-error rate and 429 rate are set per instance. It answers the analyzer's two prompts
with keyword rules, so a rehearsal batch produces a believable mix of verdicts.
"""

import asyncio
import json
import random
import re

from app.analyzer import FIND_PROMPT
from app.engine.metrics import Metrics

FIND = re.compile(r"sponsor|citizen|permanent resident|clearance|export|U\.S\. person|E-Verify|authorized to work", re.I)

# Checked in order, so a clearance someone will "sponsor" is a clearance, not a visa offer.
CLASSIFY = [
    ("security_clearance", re.compile(r"clearance", re.I)),
    ("export_control", re.compile(r"export|U\.S\. persons?", re.I)),
    ("citizens_or_permanent_residents", re.compile(r"permanent resident", re.I)),
    ("us_citizens_only", re.compile(r"citizens only", re.I)),
    ("e_verify", re.compile(r"E-Verify", re.I)),
    ("no_sponsorship", re.compile(r"without (the need for )?(employer )?sponsorship|not sponsor|unable to provide", re.I)),
    ("sponsorship_offered", re.compile(r"sponsor", re.I)),
]


class FakeAPIError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"fake HTTP {status_code}")
        self.status_code = status_code


class FakeModel:
    def __init__(
        self,
        latency: float = 0.05,
        jitter: float = 0.5,
        failure_rate: float = 0.0,
        rate_limit_rate: float = 0.0,
        seed: int | None = None,
        metrics: Metrics | None = None,
    ) -> None:
        self.metrics = metrics
        self.latency = latency
        self.jitter = jitter
        self.failure_rate = failure_rate
        self.rate_limit_rate = rate_limit_rate
        self.calls = 0
        self.in_flight = 0
        self.peak_in_flight = 0
        self._rng = random.Random(seed)

    async def complete(self, model: str, messages: list[dict], think: bool = True) -> str:
        self.calls += 1
        self.in_flight += 1
        self.peak_in_flight = max(self.peak_in_flight, self.in_flight)
        try:
            await asyncio.sleep(self.latency * self._rng.uniform(1 - self.jitter, 1 + self.jitter))
            roll = self._rng.random()
            if roll < self.rate_limit_rate:
                raise FakeAPIError(429)
            if roll < self.rate_limit_rate + self.failure_rate:
                raise FakeAPIError(503)
            system, user = messages[0]["content"], messages[1]["content"]
            reply = _find(user) if system == FIND_PROMPT else _classify(user)
            if self.metrics:
                # About four characters per token, so the dashboard's tokens per second moves in rehearsals.
                self.metrics.inc("tokens_in", (len(system) + len(user)) // 4)
                self.metrics.inc("tokens_out", len(reply) // 4)
            return reply
        finally:
            self.in_flight -= 1


def _find(posting: str) -> str:
    lines = [line.strip() for line in posting.splitlines() if line.strip()]
    company = lines[0].split(" - ")[0].split(" is hiring")[0] if lines else None
    return json.dumps({"company": company, "sentences": [line.lstrip("- ") for line in lines if FIND.search(line)]})


def _classify(numbered: str) -> str:
    signals = []
    for line in numbered.splitlines():
        sentence = re.sub(r"^\d+\.\s*", "", line).strip()
        kind = next((kind for kind, pattern in CLASSIFY if pattern.search(sentence)), "not_relevant")
        signals.append({"type": kind, "quote": sentence, "reading": f"Fake reading: {kind.replace('_', ' ')}."})
    return json.dumps({"signals": signals})
