"""The verdict rules table, as code. The model only finds signals; this module decides.

Strictest wins, except that a posting contradicting itself (offering sponsorship and also
ruling it out) gives Unclear for any status the contradiction affects.
"""

from app.schemas import Analysis, Label, Signal, SignalType, Status, Verdict

S = Status
C, U, B = Label.CLEAR, Label.UNCLEAR, Label.BLOCKED

TABLE: dict[SignalType, dict[Status, Label]] = {
    SignalType.SPONSORSHIP_OFFERED: {S.EAD: C, S.OPT: C, S.H1B: C, S.GREEN_CARD: C},
    SignalType.NO_SPONSORSHIP: {S.EAD: C, S.OPT: B, S.H1B: B, S.GREEN_CARD: C},
    SignalType.US_CITIZENS_ONLY: {S.EAD: B, S.OPT: B, S.H1B: B, S.GREEN_CARD: B},
    SignalType.SECURITY_CLEARANCE: {S.EAD: B, S.OPT: B, S.H1B: B, S.GREEN_CARD: B},
    SignalType.EXPORT_CONTROL: {S.EAD: B, S.OPT: B, S.H1B: B, S.GREEN_CARD: C},
    SignalType.CITIZENS_OR_PERMANENT_RESIDENTS: {S.EAD: B, S.OPT: B, S.H1B: B, S.GREEN_CARD: C},
}

# The posting says nothing about work authorization (E-Verify alone counts as nothing).
SILENT: dict[Status, Label] = {S.EAD: C, S.OPT: U, S.H1B: U, S.GREEN_CARD: C}

# Signals that contradict an offer of sponsorship.
CONTRADICTS_OFFER = {
    SignalType.NO_SPONSORSHIP,
    SignalType.US_CITIZENS_ONLY,
    SignalType.CITIZENS_OR_PERMANENT_RESIDENTS,
}

STRICTNESS = {C: 0, U: 1, B: 2}

STATUS_NAMES = {
    S.EAD: "an EAD",
    S.OPT: "OPT or STEM OPT",
    S.H1B: "an H-1B",
    S.GREEN_CARD: "a green card",
}


def decide(analysis: Analysis, status: Status) -> Verdict:
    deciding = [s for s in analysis.signals if s.type in TABLE]
    notes = _notes(analysis.signals, status)

    if analysis.unverified_quotes:
        notes.append("Some of the model's quotes could not be found in the posting, so they were not used.")
        return _verdict(status, U, [], notes)

    if not deciding:
        return _verdict(status, SILENT[status], [], notes)

    types = {s.type for s in deciding}
    contradicting = [s for s in deciding if s.type in CONTRADICTS_OFFER]
    if SignalType.SPONSORSHIP_OFFERED in types and contradicting:
        offer = [s for s in deciding if s.type == SignalType.SPONSORSHIP_OFFERED]
        labels = {TABLE[s.type][status] for s in offer + contradicting}
        if len(labels) > 1:
            notes.append("The posting contradicts itself about sponsorship.")
            return _verdict(status, U, offer + contradicting, notes)

    label = max((TABLE[s.type][status] for s in deciding), key=STRICTNESS.__getitem__)
    return _verdict(status, label, [s for s in deciding if TABLE[s.type][status] == label], notes)


def _notes(signals: list[Signal], status: Status) -> list[str]:
    """Edge cases the table cannot express. They inform the reader and never change the label."""
    types = {s.type for s in signals}
    notes = []
    if status == S.OPT and SignalType.E_VERIFY in types:
        notes.append("The employer uses E-Verify, which a STEM OPT extension requires.")
    if status == S.EAD and SignalType.EXPORT_CONTROL in types:
        notes.append(
            "If your EAD comes from asylee or refugee status, export rules count you as a U.S. person, "
            "so the export-control line may not apply to you."
        )
    if status == S.EAD and SignalType.NO_SPONSORSHIP in types:
        notes.append(
            "If your EAD depends on a spouse's visa (such as H-4 or L-2), it ends with that visa, "
            "and this employer will not sponsor you later."
        )
    return notes


def _verdict(status: Status, label: Label, deciding: list[Signal], notes: list[str]) -> Verdict:
    return Verdict(status=status, label=label, deciding=deciding, notes=notes, next_step=_next_step(status, label))


def _next_step(status: Status, label: Label) -> str:
    name = STATUS_NAMES[status]
    if label == C:
        return f"Nothing in the posting rules out applying with {name}. Apply, and confirm with the recruiter if unsure."
    if label == B:
        return f"The quoted lines rule out applying with {name}. Skip this one unless the recruiter says otherwise."
    return f"The posting does not settle whether {name} works here. Ask the recruiter before applying, and see the company context."
