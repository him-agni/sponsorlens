import pytest

from app import glance
from app.glance import FactKind, read_glance, supports
from app.recent import Recent
from test_analyzer import ScriptedModel

POSTING = """<p>Senior Data Engineer, Austin, TX</p>
<p>This is a hybrid role with 3 days a week in our Austin office.</p>
<p>You have 5+ years of experience with Python and Spark.</p>
<p>The base salary range is $150,000 - $180,000.</p>"""


@pytest.fixture(autouse=True)
def forget_glances(monkeypatch) -> None:
    monkeypatch.setattr(glance, "_seen", Recent())


async def test_facts_are_kept_only_with_a_real_quote() -> None:
    model = ScriptedModel(
        {
            "facts": [
                {"kind": "work_mode", "value": "Hybrid, 3 days", "quote": "hybrid role with 3 days a week in our Austin office"},
                {"kind": "salary", "value": "$150k-$180k", "quote": "The base salary range is $150,000 - $180,000"},
                {"kind": "education", "value": "PhD", "quote": "A PhD is required"},
                {"kind": "work_mode", "value": "Remote", "quote": "Senior Data Engineer"},
                {"kind": "employment_type", "value": "Full-time", "quote": "You have 5+ years of experience"},
                {"kind": "experience", "value": "hybrid, 3 days", "quote": "This is a hybrid role with 3 days a week"},
                {"kind": "visa", "value": "None", "quote": "Austin, TX"},
            ]
        }
    )
    found = await read_glance(model, "nano", POSTING)
    assert [(f.kind, f.value) for f in found.facts] == [(FactKind.WORK_MODE, "Hybrid, 3 days"), (FactKind.SALARY, "$150k-$180k")]
    # Quick and cheap: reasoning is off for this call.
    assert model.thinking == [False]


def test_a_quote_must_back_its_answer() -> None:
    assert supports("The base salary range is $150,000 - $180,000", "$150k-$180k")
    assert supports("Job Location Herndon", "Herndon, VA")
    assert not supports("You'll play a critical role in safeguarding", "full-time")


async def test_a_posting_is_read_once() -> None:
    model = ScriptedModel({"facts": []})
    await read_glance(model, "nano", POSTING)
    await read_glance(model, "nano", POSTING)
    assert len(model.calls) == 1


async def test_a_failed_read_hides_the_card() -> None:
    assert await read_glance(ScriptedModel("no json here"), "nano", POSTING) is None
