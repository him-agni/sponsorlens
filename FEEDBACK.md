# Feedback on Nebius Token Factory and NVIDIA tools

Running notes for the hackathon feedback form. Add to it as things come up.

## Setup (Phase 0)

- Credits claimed: $25 from the Devpost promo code arrived Oct 24; the Builder Program credit is still pending (told up to 2 business days)
- Token Factory base URL: `https://api.tokenfactory.nebius.com/v1/`
- Nemotron model IDs, from the public catalog (`/api/public/models_info`), Oct 23:

  | Model | ID | $ per 1M in / out | Context | Listed speed |
  | --- | --- | --- | --- | --- |
  | Nemotron 3 Nano | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` | 0.06 / 0.24 | 262K | 60 tok/s |
  | Nemotron 3 Ultra | `nvidia/Nemotron-3-Ultra-550b-a55b` | 1 / 3 | 1M | 523 tok/s |
  | Nemotron 3.5 Lightning | `nvidia/Nemotron-3_5-Lightning` | 0.06 / 0.24 | 1M | 314 tok/s |
  | Nemotron 3 Super | `nvidia/nemotron-3-super-120b-a12b` | 0.3 / 0.9 | 256K | 127 tok/s |

- Rate limits: dynamic. The docs show an example baseline of 60 RPM and 400K TPM, scaling ×1.2 per 15-minute window of ≥80% use, up to 20× base. Actual limits for this key on Oct 24, from the response headers:

  | Model | Requests per minute | Tokens per minute |
  | --- | --- | --- |
  | Nano | 100 | 800,000 |
  | Ultra | 300 | 200,000 |

  Limits are per model, and Ultra's TPM is the tightest.
- JSON or structured output: the API supports `response_format` `json_object` and `json_schema`, but none of the Nemotron models carry the "JSON mode" tag in the catalog. In practice both Nano and Ultra accepted `json_object` and returned valid JSON, so SponsorLens uses it and still parses defensively.
- Reasoning: both models return reasoning separately from the answer, but in differently named fields: Nano uses `message.reasoning`, Ultra uses `message.reasoning_content`.
- First-call latency (short ping): Nano 3.1 s for 131 completion tokens; Ultra 1.1 s for 109 completion tokens. The reasoning tokens are billed as completion tokens even though the reply is one sentence.

## Phase 1: verdicts (Oct 24)

- Prompt p1 passed the eval on the first try: 15 of 15 fixtures right for all four statuses, 0 unverified quotes, 72 s for the run at concurrency 3 (2.5 to 16.5 s per posting).
- The hard cases all worked: sponsorship listed only under benefits, "ability to obtain" a clearance, a posting that contradicts itself, "sponsor" meaning a clearance, and "sponsor" meaning events.
- Without JSON mode, Nano answered a posting with no matches with a bare `[]` instead of the requested object; with `json_object` it returned the right shape.
- The one quote flaw was ours: flattening the posting to one line let a heading ("Legal") join the next sentence in a quote. Keeping line breaks fixed it.
- Token Factory returned intermittent `503 Service Temporarily Unavailable` pages from nginx for a few minutes on Oct 24, even after the SDK's two retries. It recovered on its own. This makes the Phase 2 retry layer a must, not a nice-to-have.

## Phase 4: a 200-posting live run (Oct 27)

- 200 real postings from 20 public Greenhouse boards through Nano then Ultra cost $0.30: 303 calls, 348K tokens in, 474K out. Most of the output was reasoning, which is billed as output.
- Latency had a long tail: p50 6.4 s, p95 79 s, max 101 s per call, all from reasoning length. The answer itself is a few hundred tokens.
- 3 of 200 calls came back with no JSON at all. One long posting used 3,066 reasoning tokens on Nano, so with `max_tokens` 4096 the reasoning sometimes used up the budget before the answer started. Raising the cap and retrying fixed it. A per-request reasoning budget, separate from `max_tokens`, would make this predictable.
- Turning reasoning off (`chat_template_kwargs: {enable_thinking: false}`) made Nano 3× faster but it copied an irrelevant sentence, so reasoning stays on. It was not obvious from the docs which reasoning controls Token Factory honors for Nemotron.
- No 429s at 8 concurrent calls, and no 5xx during this run.
- The Builder Program credit never arrived before the deadline week, so the whole build ran on the $25 promo credit, which was plenty.

## What worked well

- The public model catalog JSON and the `llms.txt` docs index made it possible to plan model choice and rate limits before having a key.

## What was confusing or missing

- The catalog page at tokenfactory.nebius.com/models renders client-side, so the model IDs are only easy to find through `/model-catalog.md` or `/api/public/models_info`.
- Model ID casing is inconsistent across the catalog (`NVIDIA-Nemotron-3-Nano-30B-A3B`, `nemotron-3-super-120b-a12b`, `Nemotron-3_5-Lightning`), which makes typos likely.
- Nemotron models are tagged for function calling but not JSON mode, and the docs do not say whether `response_format` is ignored, rejected or honored for them. (It turned out to be honored.)
- The reasoning field name differs between Nano (`reasoning`) and Ultra (`reasoning_content`), so code that reads reasoning has to handle both.

## Suggestions
