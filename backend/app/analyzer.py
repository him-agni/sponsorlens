"""The Nemotron cascade: Nano finds candidate sentences, Ultra turns them into signals.

Every quote is checked against the normalized posting. A reply that is not valid JSON, or that
quotes text the posting does not contain, is retried once with the problem spelled out.
"""

import json
import re
from typing import Literal

from pydantic import BaseModel, ValidationError

from app.llm import ChatModel
from app.normalize import normalize, quote_in_text
from app.schemas import Analysis, Signal, SignalType

PROMPT_VERSION = "p1"

FIND_PROMPT = """You read US job postings and copy out sentences about work authorization.

Copy every sentence or bullet that mentions any of: visa sponsorship, immigration, H-1B, OPT, EAD, \
citizenship, permanent residency or green cards, security clearances, export control (ITAR, EAR, \
"U.S. person"), E-Verify, or being authorized or eligible to work in the US. Look in every section, \
including benefits and legal footers. Ignore other meanings of "sponsor", such as sponsoring events.

Copy each sentence exactly as written, character for character. Do not fix, shorten or merge them.

Reply with JSON only, no other text:
{"company": "<employer name, or null>", "sentences": ["<exact sentence>", ...]}
If there are no such sentences, reply with an empty list."""

CLASSIFY_PROMPT = """You classify sentences from a US job posting by what they say about work authorization.

Types:
- sponsorship_offered: the employer will sponsor work visas (H-1B, transfers, green cards), \
including as a listed benefit.
- no_sponsorship: the employer will not sponsor visas, now or in the future, or candidates must \
work without sponsorship.
- us_citizens_only: only US citizens may apply.
- security_clearance: a security clearance is required, or the candidate must be able to obtain one. \
Sponsoring someone for a clearance is this type, not sponsorship_offered.
- export_control: candidates must be "U.S. persons" under export rules (ITAR, EAR).
- citizens_or_permanent_residents: only US citizens or permanent residents (green card holders) may apply.
- e_verify: the employer participates in E-Verify.
- not_relevant: none of the above, such as a generic equal-opportunity statement.

For each relevant statement, give the type, the shortest exact quote from the sentence that carries \
the meaning (copied character for character), and a one-sentence plain reading for a job seeker. \
One sentence can hold more than one statement.

Reply with JSON only, no other text:
{"signals": [{"type": "<type>", "quote": "<exact quote>", "reading": "<plain reading>"}]}"""

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


class _Found(BaseModel):
    company: str | None = None
    sentences: list[str] = []


class _RawSignal(BaseModel):
    type: SignalType | Literal["not_relevant"]
    quote: str
    reading: str = ""


class _Classified(BaseModel):
    signals: list[_RawSignal] = []


class Analyzer:
    def __init__(self, model: ChatModel, nano_model: str, ultra_model: str) -> None:
        self.model = model
        self.nano_model = nano_model
        self.ultra_model = ultra_model

    async def analyze(self, posting: str) -> Analysis:
        text = normalize(posting)
        found, missing_sentences = await self._find(text)
        analysis = Analysis(
            company=found.company,
            nano_model=self.nano_model,
            ultra_model=self.ultra_model,
            prompt_version=PROMPT_VERSION,
        )
        if found.sentences:
            analysis.signals, missing_quotes = await self._classify(text, found.sentences)
        else:
            missing_quotes = 0
        analysis.unverified_quotes = missing_sentences + missing_quotes
        return analysis

    async def _find(self, text: str) -> tuple[_Found, int]:
        messages = [{"role": "system", "content": FIND_PROMPT}, {"role": "user", "content": text}]
        found = await self._ask(self.nano_model, messages, _Found)
        missing = [s for s in found.sentences if not quote_in_text(s, text)]
        if missing:
            found = await self._ask(self.nano_model, _with_correction(messages, found, missing), _Found)
            missing = [s for s in found.sentences if not quote_in_text(s, text)]
        found.sentences = [s for s in found.sentences if quote_in_text(s, text)]
        return found, len(missing)

    async def _classify(self, text: str, sentences: list[str]) -> tuple[list[Signal], int]:
        numbered = "\n".join(f"{i}. {s}" for i, s in enumerate(sentences, 1))
        messages = [{"role": "system", "content": CLASSIFY_PROMPT}, {"role": "user", "content": numbered}]
        classified = await self._ask(self.ultra_model, messages, _Classified)
        missing = [s.quote for s in _relevant(classified) if not quote_in_text(s.quote, text)]
        if missing:
            classified = await self._ask(self.ultra_model, _with_correction(messages, classified, missing), _Classified)
            missing = [s.quote for s in _relevant(classified) if not quote_in_text(s.quote, text)]
        signals = [
            Signal(type=s.type, quote=s.quote, reading=s.reading)
            for s in _relevant(classified)
            if quote_in_text(s.quote, text)
        ]
        return signals, len(missing)

    async def _ask[T: BaseModel](self, model: str, messages: list[dict], schema: type[T]) -> T:
        """Retry an unusable reply up to twice. A reply with no JSON at all usually means the reasoning
        used up the token budget, so it is asked again as it was; a malformed one is shown its error."""
        reply = await self.model.complete(model, messages)
        for retries_left in (2, 1, 0):
            try:
                return schema.model_validate(_parse_json(reply))
            except (ValueError, ValidationError) as error:
                if not retries_left:
                    raise
                retry = messages
                if "{" in reply:
                    retry = messages + [
                        {"role": "assistant", "content": reply},
                        {"role": "user", "content": f"That reply was not valid ({error}). Reply with the JSON only."},
                    ]
                reply = await self.model.complete(model, retry)
        raise AssertionError("unreachable")


def _relevant(classified: _Classified) -> list[_RawSignal]:
    return [s for s in classified.signals if s.type != "not_relevant"]


def _with_correction(messages: list[dict], reply: BaseModel, missing: list[str]) -> list[dict]:
    listed = "\n".join(f"- {m}" for m in missing)
    return messages + [
        {"role": "assistant", "content": reply.model_dump_json()},
        {
            "role": "user",
            "content": f"These are not exact copies of the posting text:\n{listed}\n"
            "Copy them again character for character, or leave them out. Reply with the full JSON.",
        },
    ]


def _parse_json(reply: str) -> object:
    """Nemotron may wrap its JSON in reasoning or a code fence; take the outermost object."""
    reply = _THINK.sub("", reply)
    start, end = reply.find("{"), reply.rfind("}")
    if start == -1 or end < start:
        raise ValueError("no JSON object in reply")
    return json.loads(reply[start : end + 1])
