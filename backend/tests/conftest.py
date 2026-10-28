import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def no_end_date(monkeypatch) -> None:
    """The hosted demo stops live calls after its last day; tests must pass whatever today's date is."""
    monkeypatch.setattr(settings, "live_until", None)
