import pytest

from app.rules import decide
from app.schemas import Analysis, Label, Signal, SignalType, Status

C, U, B = Label.CLEAR, Label.UNCLEAR, Label.BLOCKED
STATUSES = [Status.EAD, Status.OPT, Status.H1B, Status.GREEN_CARD]


def sig(type_: SignalType) -> Signal:
    return Signal(type=type_, quote=f"quote for {type_}", reading="reading")


def labels(*types: SignalType, unverified: int = 0) -> list[Label]:
    analysis = Analysis(signals=[sig(t) for t in types], unverified_quotes=unverified)
    return [decide(analysis, status).label for status in STATUSES]


# One case per row of the rules table, columns in order: EAD, OPT, H-1B, green card.
@pytest.mark.parametrize(
    ("signal", "expected"),
    [
        (SignalType.SPONSORSHIP_OFFERED, [C, C, C, C]),
        (SignalType.NO_SPONSORSHIP, [C, B, B, C]),
        (SignalType.US_CITIZENS_ONLY, [B, B, B, B]),
        (SignalType.SECURITY_CLEARANCE, [B, B, B, B]),
        (SignalType.EXPORT_CONTROL, [B, B, B, C]),
        (SignalType.CITIZENS_OR_PERMANENT_RESIDENTS, [B, B, B, C]),
    ],
)
def test_table_row(signal: SignalType, expected: list[Label]) -> None:
    assert labels(signal) == expected


def test_silent_posting() -> None:
    assert labels() == [C, U, U, C]


def test_e_verify_alone_counts_as_silent_with_an_opt_note() -> None:
    assert labels(SignalType.E_VERIFY) == [C, U, U, C]
    analysis = Analysis(signals=[sig(SignalType.E_VERIFY)])
    assert decide(analysis, Status.OPT).notes
    assert not decide(analysis, Status.H1B).notes


def test_ead_edge_cases_add_notes_without_changing_the_label() -> None:
    export = decide(Analysis(signals=[sig(SignalType.EXPORT_CONTROL)]), Status.EAD)
    assert export.label == B
    assert any("asylee" in n for n in export.notes)

    no_sponsorship = decide(Analysis(signals=[sig(SignalType.NO_SPONSORSHIP)]), Status.EAD)
    assert no_sponsorship.label == C
    assert any("H-4" in n for n in no_sponsorship.notes)

    assert not decide(Analysis(signals=[sig(SignalType.NO_SPONSORSHIP)]), Status.GREEN_CARD).notes


def test_strictest_wins() -> None:
    assert labels(SignalType.NO_SPONSORSHIP, SignalType.EXPORT_CONTROL) == [B, B, B, C]


def test_contradiction_gives_unclear_only_where_the_signals_disagree() -> None:
    assert labels(SignalType.SPONSORSHIP_OFFERED, SignalType.NO_SPONSORSHIP) == [C, U, U, C]
    assert labels(SignalType.SPONSORSHIP_OFFERED, SignalType.US_CITIZENS_ONLY) == [U, U, U, U]


def test_clearance_beats_an_offer_of_sponsorship() -> None:
    assert labels(SignalType.SPONSORSHIP_OFFERED, SignalType.SECURITY_CLEARANCE) == [B, B, B, B]


def test_unverified_quotes_give_unclear() -> None:
    assert labels(SignalType.SPONSORSHIP_OFFERED, unverified=1) == [U, U, U, U]


def test_deciding_signals_are_the_ones_that_set_the_label() -> None:
    analysis = Analysis(signals=[sig(SignalType.NO_SPONSORSHIP), sig(SignalType.EXPORT_CONTROL)])
    verdict = decide(analysis, Status.EAD)
    assert verdict.label == B
    assert {s.type for s in verdict.deciding} == {SignalType.EXPORT_CONTROL}
