import pytest

from app.normalize import normalize
from app.rules import decide
from app.schemas import Analysis, Signal
from app.fixtures import load_fixtures, load_hard_cases

FIXTURES = load_fixtures()
ALL_CASES = FIXTURES + load_hard_cases()


def test_there_are_fifteen_fixtures_with_unique_ids() -> None:
    assert len(FIXTURES) == 15
    assert len({f.id for f in ALL_CASES}) == len(ALL_CASES)


@pytest.mark.parametrize("fixture", ALL_CASES, ids=lambda f: f.id)
def test_expected_verdicts_follow_the_rules_table(fixture) -> None:
    """Catches a typo in the fixture file, so eval failures always mean the model got it wrong."""
    analysis = Analysis(signals=[Signal(type=t, quote="q", reading="r") for t in fixture.signals])
    assert {status: decide(analysis, status).label for status in fixture.expected} == fixture.expected


@pytest.mark.parametrize("fixture", ALL_CASES, ids=lambda f: f.id)
def test_fixture_text_survives_normalization(fixture) -> None:
    assert normalize(fixture.posting)
