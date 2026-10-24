from enum import StrEnum

from pydantic import BaseModel, Field


class Status(StrEnum):
    """The reader's work-authorization status, picked from the dropdown."""

    EAD = "ead"
    OPT = "opt"
    H1B = "h1b"
    GREEN_CARD = "green_card"


class SignalType(StrEnum):
    """One row of the rules table. The model may only use these types."""

    SPONSORSHIP_OFFERED = "sponsorship_offered"
    NO_SPONSORSHIP = "no_sponsorship"
    US_CITIZENS_ONLY = "us_citizens_only"
    SECURITY_CLEARANCE = "security_clearance"
    EXPORT_CONTROL = "export_control"
    CITIZENS_OR_PERMANENT_RESIDENTS = "citizens_or_permanent_residents"
    E_VERIFY = "e_verify"


class Label(StrEnum):
    CLEAR = "clear"
    UNCLEAR = "unclear"
    BLOCKED = "blocked"


class Signal(BaseModel):
    type: SignalType
    quote: str = Field(description="Exact text copied from the posting")
    reading: str = Field(description="What the quote means for a job seeker, in plain language")


class Analysis(BaseModel):
    """What the model found in one posting. It holds no status, so one analysis serves every status."""

    company: str | None = None
    signals: list[Signal] = []
    unverified_quotes: int = 0
    nano_model: str = ""
    ultra_model: str = ""
    prompt_version: str = ""


class Verdict(BaseModel):
    status: Status
    label: Label
    deciding: list[Signal] = []
    notes: list[str] = []
    next_step: str
