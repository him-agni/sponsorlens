import pytest

from app.analyzer import Analyzer
from app.engine.fake_model import FakeAPIError, FakeModel
from app.fixtures import load_fixtures
from app.rules import decide


async def test_fake_answers_give_believable_verdicts() -> None:
    """Not an accuracy test: it checks rehearsals produce the expected mix on the easy fixtures."""
    analyzer = Analyzer(FakeModel(latency=0), "fake-nano", "fake-ultra")
    easy = [f for f in load_fixtures() if f.id[:3] in {"f01", "f02", "f03", "f05", "f06", "f08", "f13"}]
    for fixture in easy:
        analysis = await analyzer.analyze(fixture.posting)
        assert analysis.unverified_quotes == 0, fixture.id
        assert {s: decide(analysis, s).label for s in fixture.expected} == fixture.expected, fixture.id


async def test_injected_rate_limits_and_failures() -> None:
    always_429 = FakeModel(latency=0, rate_limit_rate=1.0)
    with pytest.raises(FakeAPIError) as error:
        await always_429.complete("m", [{"content": ""}, {"content": ""}])
    assert error.value.status_code == 429

    always_down = FakeModel(latency=0, failure_rate=1.0)
    with pytest.raises(FakeAPIError) as error:
        await always_down.complete("m", [{"content": ""}, {"content": ""}])
    assert error.value.status_code == 503


async def test_seeded_runs_repeat() -> None:
    async def outcomes(seed: int) -> list[str]:
        model, results = FakeModel(latency=0, rate_limit_rate=0.3, seed=seed), []
        for _ in range(20):
            try:
                await model.complete("m", [{"content": ""}, {"content": "1. x"}])
                results.append("ok")
            except FakeAPIError as error:
                results.append(str(error.status_code))
        return results

    assert await outcomes(7) == await outcomes(7)
    assert "429" in await outcomes(7)
