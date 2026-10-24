"""Run the fixtures through the real Nemotron cascade and score the verdicts.

Run from backend/: uv run python -m scripts.eval [--only f09] [--concurrency 3]
Phase 1 gate: at least 12 of 15 fixtures right for all four statuses, with zero unverified quotes.
"""

import argparse
import asyncio
import sys
import time

from app.analyzer import PROMPT_VERSION, Analyzer
from app.config import settings
from app.fixtures import Fixture, load_fixtures
from app.llm import TokenFactoryModel
from app.rules import decide
from app.schemas import Analysis

GATE_PASSES = 12


async def run_one(analyzer: Analyzer, fixture: Fixture, limit: asyncio.Semaphore) -> tuple[Analysis | None, float, str]:
    async with limit:
        start = time.perf_counter()
        try:
            analysis = await analyzer.analyze(fixture.posting)
        except Exception as error:
            return None, time.perf_counter() - start, f"{type(error).__name__}: {error}"
        return analysis, time.perf_counter() - start, ""


def report(fixture: Fixture, analysis: Analysis | None, seconds: float, error: str) -> bool:
    if analysis is None:
        print(f"FAIL {fixture.id}  ({seconds:.1f}s)\n     error: {error}")
        return False

    cells, passed = [], True
    for status, expected in fixture.expected.items():
        got = decide(analysis, status).label
        passed &= got == expected
        cells.append(f"{status}={got}" if got == expected else f"{status}={got} (want {expected})")

    found = sorted(s.type.value for s in analysis.signals)
    want = sorted(s.value for s in fixture.signals)
    print(f"{'PASS' if passed else 'FAIL'} {fixture.id}  ({seconds:.1f}s)")
    print(f"     {'  '.join(cells)}")
    if found != want:
        print(f"     signals: found {found}, want {want}")
    for signal in analysis.signals:
        print(f"     - {signal.type}: \"{signal.quote}\"")
    if analysis.unverified_quotes:
        print(f"     unverified quotes: {analysis.unverified_quotes}")
    return passed


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="run fixtures whose id starts with this")
    parser.add_argument("--concurrency", type=int, default=3)
    args = parser.parse_args()

    if not settings.nebius_api_key or not settings.nano_model or not settings.ultra_model:
        print("Set NEBIUS_API_KEY, NANO_MODEL and ULTRA_MODEL in .env first.")
        return 2

    fixtures = [f for f in load_fixtures() if not args.only or f.id.startswith(args.only)]
    analyzer = Analyzer(TokenFactoryModel(), settings.nano_model, settings.ultra_model)
    limit = asyncio.Semaphore(args.concurrency)
    results = await asyncio.gather(*(run_one(analyzer, f, limit) for f in fixtures))

    passes = sum(report(f, *result) for f, result in zip(fixtures, results))
    unverified = sum(a.unverified_quotes for a, _, _ in results if a)
    gate = passes >= min(GATE_PASSES, len(fixtures)) and unverified == 0
    print(f"\n{passes}/{len(fixtures)} fixtures pass all four statuses, {unverified} unverified quotes")
    print(f"prompt {PROMPT_VERSION}, nano={settings.nano_model}, ultra={settings.ultra_model}")
    print(f"Phase 1 gate: {'PASS' if gate else 'FAIL'}")
    return 0 if gate else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
