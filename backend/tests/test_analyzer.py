import json

from app.analyzer import Analyzer
from app.schemas import SignalType

POSTING = """<p>Acme Robotics is hiring.</p>
<p>Applicants must be authorized to work in the U.S. without sponsorship, now or in the future.</p>
<p>We participate in E‑Verify.</p>"""

NO_SPONSORSHIP = "Applicants must be authorized to work in the U.S. without sponsorship, now or in the future."


class ScriptedModel:
    """Returns canned replies in order and records every call."""

    def __init__(self, *replies: object) -> None:
        self.replies = [r if isinstance(r, str) else json.dumps(r) for r in replies]
        self.calls: list[tuple[str, list[dict]]] = []

    async def complete(self, model: str, messages: list[dict]) -> str:
        self.calls.append((model, messages))
        return self.replies.pop(0)


def analyzer(model: ScriptedModel) -> Analyzer:
    return Analyzer(model, nano_model="nano", ultra_model="ultra")


async def test_two_step_cascade() -> None:
    model = ScriptedModel(
        {"company": "Acme Robotics", "sentences": [NO_SPONSORSHIP, "We participate in E-Verify."]},
        {
            "signals": [
                {"type": "no_sponsorship", "quote": "without sponsorship, now or in the future", "reading": "r"},
                {"type": "e_verify", "quote": "We participate in E-Verify", "reading": "r"},
            ]
        },
    )
    analysis = await analyzer(model).analyze(POSTING)

    assert [m for m, _ in model.calls] == ["nano", "ultra"]
    assert analysis.company == "Acme Robotics"
    assert [s.type for s in analysis.signals] == [SignalType.NO_SPONSORSHIP, SignalType.E_VERIFY]
    assert analysis.unverified_quotes == 0


async def test_no_candidates_skips_ultra() -> None:
    model = ScriptedModel({"company": "Acme Robotics", "sentences": []})
    analysis = await analyzer(model).analyze("Acme Robotics is hiring a welder.")
    assert len(model.calls) == 1
    assert analysis.signals == []


async def test_reasoning_and_code_fence_are_stripped() -> None:
    reply = '<think>The posting has no {such} lines.</think>```json\n{"company": null, "sentences": []}\n```'
    analysis = await analyzer(ScriptedModel(reply)).analyze("Some posting.")
    assert analysis.company is None


async def test_invalid_json_is_retried_once() -> None:
    model = ScriptedModel("not json", {"company": "Acme", "sentences": []})
    analysis = await analyzer(model).analyze("Some posting.")
    assert analysis.company == "Acme"
    assert "not valid" in model.calls[1][1][-1]["content"]


async def test_invented_quote_is_retried_then_counted() -> None:
    invented = {"signals": [{"type": "sponsorship_offered", "quote": "We sponsor H-1B visas", "reading": "r"}]}
    model = ScriptedModel({"company": "Acme", "sentences": [NO_SPONSORSHIP]}, invented, invented)
    analysis = await analyzer(model).analyze(POSTING)

    assert len(model.calls) == 3
    assert analysis.signals == []
    assert analysis.unverified_quotes == 1


async def test_invented_quote_fixed_on_retry() -> None:
    model = ScriptedModel(
        {"company": "Acme", "sentences": [NO_SPONSORSHIP]},
        {"signals": [{"type": "no_sponsorship", "quote": "no sponsorship ever", "reading": "r"}]},
        {"signals": [{"type": "no_sponsorship", "quote": "without sponsorship", "reading": "r"}]},
    )
    analysis = await analyzer(model).analyze(POSTING)
    assert [s.type for s in analysis.signals] == [SignalType.NO_SPONSORSHIP]
    assert analysis.unverified_quotes == 0


async def test_not_relevant_signals_are_dropped() -> None:
    model = ScriptedModel(
        {"company": "Acme", "sentences": ["We participate in E-Verify."]},
        {"signals": [{"type": "not_relevant", "quote": "made up", "reading": ""}]},
    )
    analysis = await analyzer(model).analyze(POSTING)
    assert analysis.signals == []
    assert analysis.unverified_quotes == 0
