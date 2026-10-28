"""At a glance: the other things that decide whether to apply, each quoted from the posting.

Location, work mode, experience, education, salary and employment type. It is read in one quick Nano
call beside the verdict, never changes the verdict, and a failure here only hides the card.
"""

import logging
import re
from collections import OrderedDict
from enum import StrEnum

from pydantic import BaseModel, ValidationError

from app.analyzer import _parse_json
from app.engine.cache import content_hash
from app.llm import ChatModel
from app.normalize import normalize, quote_in_text

log = logging.getLogger(__name__)


class FactKind(StrEnum):
    LOCATION = "location"
    WORK_MODE = "work_mode"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    SALARY = "salary"
    EMPLOYMENT_TYPE = "employment_type"


class Fact(BaseModel):
    kind: FactKind
    # A few words, e.g. "Hybrid, 3 days in office" or "5+ years".
    value: str
    quote: str


class Glance(BaseModel):
    facts: list[Fact]


GLANCE_PROMPT = """You read a US job posting and pull out the practical facts a candidate checks before applying.

Reply with JSON only: {"facts": [{"kind": ..., "value": ..., "quote": ...}]}

kind is one of:
- "location": where the job is based
- "work_mode": remote, hybrid or on-site, and any in-office days
- "experience": years or level of experience required
- "education": degree required
- "salary": the pay range
- "employment_type": full-time, part-time, contract or internship

value is a short plain answer of at most six words, such as "Hybrid, 3 days in office" or "5+ years".
quote is copied word for word from the posting, and must contain the fact.
Include a kind only if the posting states it, and at most one fact per kind. Never guess."""

# Kept for the life of the process, like the verdict cache, so a repeated posting costs nothing.
_seen: OrderedDict[str, Glance] = OrderedDict()
_CAPACITY = 1024


async def read_glance(model: ChatModel, nano_model: str, text: str) -> Glance | None:
    normalized = normalize(text)
    key = content_hash(normalized)
    if key in _seen:
        _seen.move_to_end(key)
        return _seen[key]
    messages = [{"role": "system", "content": GLANCE_PROMPT}, {"role": "user", "content": normalized}]
    try:
        # Reasoning off: these facts are stated plainly, and the card should not slow the verdict.
        raw = _parse_json(await model.complete(nano_model, messages, think=False))
    except Exception:
        log.warning("At-a-glance read failed", exc_info=True)
        return None
    facts: dict[FactKind, Fact] = {}
    for item in raw.get("facts", []) if isinstance(raw, dict) else []:
        try:
            fact = Fact.model_validate(item)
        except ValidationError:
            continue
        # Same rule as the verdict: a fact is shown only if its quote is really in the posting, and the
        # quote must back the answer (on Oct 28 Nano gave "full-time" with a quote that never said so).
        # One fact per row: Nano once gave "MS or PhD" as both education and experience.
        repeated = any(f.value.casefold() == fact.value.casefold() for f in facts.values())
        if fact.kind not in facts and not repeated and quote_in_text(fact.quote, normalized) and supports(fact.quote, fact.value):
            facts[fact.kind] = fact
    glance = Glance(facts=list(facts.values()))
    _seen[key] = glance
    if len(_seen) > _CAPACITY:
        _seen.popitem(last=False)
    return glance


def supports(quote: str, value: str) -> bool:
    """True if a number, or a word of three letters or more, from the answer appears in the quote."""
    words = _WORDS.findall(value.lower())
    quoted = quote.lower()
    return any(word in quoted for word in words if word.isdigit() or len(word) >= 3)


_WORDS = re.compile(r"[a-z]+|\d+")
