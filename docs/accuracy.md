# Accuracy

SponsorLens is scored in LangSmith on 27 invented US job postings. Each one is labeled with the right verdict for all four statuses (EAD, OPT, H-1B and green card).

- **15 core postings** ([`backend/fixtures/postings.json`](../backend/fixtures/postings.json)): one per rule, plus contradictions and distractors.
- **12 harder postings** ([`backend/fixtures/hard_cases.json`](../backend/fixtures/hard_cases.json)), written after testing on real postings. For example:
  - a Top Secret clearance buried in an app developer's requirements;
  - export control stated only as "U.S. person as defined in 22 CFR 120.62";
  - a refusal to "take over sponsorship";
  - an offer written as an FAQ answer;
  - "Visa sponsorship: Not available" as a header field;
  - business uses of "sponsor" and "citizen".

The postings are invented, so no real company's text is stored or uploaded.

Each setup's latest run is saved in [`backend/results/`](../backend/results/), with the expected and actual verdict, signals, quotes, cost and time for every posting. The table for each posting is in [accuracy-by-posting.md](accuracy-by-posting.md).

## Results (Oct 28, 2026, prompt p1)

| Setup | Right for all four statuses | Every quote found in the posting | Cost for all 27 | Time per posting (median, slowest) |
|---|---|---|---|---|
| **Nano finds, Ultra classifies (what the app runs)** | **27 / 27** | 27 / 27 | $0.045 | 6.6 s, 12.8 s |
| Nano for both steps | 27 / 27 | 27 / 27 | $0.007 | 9.9 s, 18.2 s |
| Ultra for both steps | 26 / 27 | 27 / 27 | $0.085 | 2.9 s, 5.4 s |
| The app's setup with reasoning off | 26 / 27 | 27 / 27 | $0.013 | 1.6 s, 3.2 s |

An earlier run the same day gave the same picture. The app's setup and Nano alone got 27 of 27 again, and reasoning-off missed the same posting. The one difference: Ultra alone got 27 of 27 that time. A model can answer the same posting differently from one run to the next, so one miss in 27 is within that variation.

## What the results show

- **No setup quoted anything that isn't in the posting.** The code checks every quote word for word before it can affect a verdict. Across all 108 runs, the model never needed that safeguard.
- **Reasoning matters.**
  - With reasoning off, the model missed "Candidates must be able to work in the US without sponsorship" in the legal footer of a posting that also offers sponsorship. It did so in both runs.
  - That gave OPT and H-1B holders a false Clear, the most harmful mistake for this audience.
  - So reasoning stays on. Reasoning off is only a fallback, used when a reasoning reply runs out of tokens.
- **Ultra alone made the opposite, safer mistake.** It read "Applicants must be legally authorized to work in the United States" as ruling out sponsorship, and answered Blocked where the posting really leaves it Unclear.
- **On these 27 postings, Nano alone was as accurate as the app's setup, at about a sixth of the cost**, but it was the slowest.
  - The set is too small to justify changing models days before the deadline, so the app keeps its setup.
  - The next step is a larger dataset labeled from real postings, to settle which setup gives the best mix of cost, speed and safety.

## Run it yourself

From `backend/`, with `NEBIUS_API_KEY` and `LANGSMITH_API_KEY` in the repo-root `.env`:

```bash
uv run python -m scripts.experiment                              # the app's setup
uv run python -m scripts.experiment --setup cascade nano-only ultra-only cascade-no-reasoning
```

What the script does:

- It uploads the dataset (`sponsorlens-postings`) to LangSmith if it has changed.
- It runs each setup as a LangSmith experiment. Each run is traced, including every Nemotron call with its prompt, reply and token counts, and experiments can be compared side by side in LangSmith.
- It saves each setup's results to `backend/results/` and rebuilds [accuracy-by-posting.md](accuracy-by-posting.md).

A run of all four setups costs about $0.15 of Nebius credit.

LangSmith is used only for these local runs. The hosted app doesn't import it, and Render installs without dev dependencies, so nothing a visitor pastes is ever sent to LangSmith.
