# SponsorLens handoff

Everything someone needs to pick this project up cold: what is done, what is live, how to run it, how the code is laid out, what was decided and why, and what comes next. Updated at every phase step; the date on each section says when it was last true.

The full plan, with its phase gates, lives in [build-plan.md](build-plan.md). This doc records where reality has got to against it.

## At a glance (Oct 28, 2026)

| | |
| --- | --- |
| What it is | Reads a US job posting and gives a verdict (Clear, Unclear, Blocked) per work-authorization status (EAD, OPT, H-1B, green card), quoting the posting as evidence. Backed by a hand-built asyncio engine |
| Hackathon | Nebius x NVIDIA Global AI Hackathon, solo entry, Best Apps and Agents track plus the Tavily prize |
| Deadline | **Fri Oct 30, 2026, 10:00am PDT.** Plan: submit Thu Oct 29 evening |
| Repo | https://github.com/him-agni/sponsorlens (public, MIT, branch `main`) |
| Web app | https://sponsorlens-web.onrender.com (Render static site) |
| API | https://sponsorlens.onrender.com (Render free web service; live Nemotron since Oct 28, under the spending limits) |
| Schedule | About one day behind the plan. Phases 0 to 4 done; Phase 5 spending limits live on Render Oct 28 |

## Phase status

| Phase | Planned | State | Gate result |
| --- | --- | --- | --- |
| P0 Setup, first model call | Fri Oct 23 | Done | `/api/ping-model` returned a Nemotron reply |
| P1 Verdict for one posting | Sat Oct 24 | Done | Eval 15/15 for all four statuses, 0 unverified quotes (prompt `p1`) |
| P2 Engine core, first deploy | Sun Oct 25 | Done Oct 27 | Rehearsal fills and drains the queues; web app reaches the API on Render ("Engine status: ok", 389 ms). Still to film: `/health` after the API wakes from sleep |
| P3 Intake, shards, cache, log | Mon Oct 26 | Done Oct 27 | `scripts/kill_test.py`: killed mid-batch at 82/200, restarted, 82 returned from the log, 117 analysed, 1 cache hit, 0 postings finished twice |
| P4 Web app and dashboard | Tue Oct 27 | Done Oct 28 | Checked in light, dark, desktop and 390 px phone width, live and sample mode, no console errors. Gate passed Oct 28: a new user (the owner's husband) used the deployed site on his phone and explained a verdict back unaided. His requests: a clear button and pasting a link (both built), and a wider scope (roadmap) |
| P5 Deploy, limits, benchmark | Wed Oct 28 | In progress | Limits deployed and keys on Render Oct 28. Checked: `/health` shows `live_batches: false`, `/metrics` shows a $0.50 budget, `POST /api/batch` is 403, one live check returned Blocked with the right quote for $0.0024. Still to do: phone check over cellular, benchmark |
| P6 Video, README, submit | Thu Oct 29 | Not started | — |

## Working rules

These come from the owner and apply to every change.

- **Authorship.** The owner (GitHub `him-agni`) is the sole author. Never add `Co-Authored-By` trailers or any AI attribution to commits, PRs or files. Commits use the noreply email `100171053+him-agni@users.noreply.github.com`, set in the repo's local git config.
- **Commits.** Small commits, one per component, prefixed with the phase (`Phase 3: ...`), each passing the tests on its own. Never one commit for a whole phase.
- **Push** only when the owner says so. Before pushing, check the unpushed commits for attribution and for keys.
- **Secrets.** API keys live only in the repo-root `.env` (gitignored). Never print them, paste them or commit them.
- **Spending.** The hosted API gets `NEBIUS_API_KEY` only after the spending limits are deployed (see Decisions, Spending limits). Engine work uses `MODEL_BACKEND=fake`.

## Accounts and credits

| Item | State |
| --- | --- |
| Nebius Token Factory | Key in `.env`. $25 promo credit (Oct 24) plus $25 from the AI Builder Program (Oct 28), so about $50 in all. Spent so far: well under $1 (eval, a 10-posting probe, the $0.30 sample run) |
| Tavily | Key in `.env` since Oct 27. Free plan (1,000 searches a month) plus $25 Builder Program credit (Oct 28) |
| LangSmith | `LANGSMITH_API_KEY` in `.env` (Oct 28). $100 Builder Program credit, Personal org, spend limit $10 a month, base 14-day retention. Planned for tracing local eval and benchmark runs only, never the hosted demo, because traces would carry pasted posting text |
| Toloka, Tandem | $50 each offered by the Builder Program; not used this week (human labeling is too slow for the deadline) |
| Render | Free tier, no card. Services: `sponsorlens` (API, created by hand because the blueprint's `sponsorlens-api` step failed) and `sponsorlens-web` (static site) |
| Render env vars | API: `CORS_ORIGINS=["https://sponsorlens-web.onrender.com"]`, `NEBIUS_API_KEY`, `TAVILY_API_KEY`, `LIVE_BATCHES=false`, `DAILY_BUDGET_USD=0.5`, `HOURLY_REQUESTS=30` (set Oct 28 through the Render API; the service was made by hand, so `render.yaml` is not applied to it). A stray `VITE_API_URL` on the API service is harmless. Web: `VITE_API_URL=https://sponsorlens.onrender.com`. Vite bakes `VITE_API_URL` in at build time, so changing it needs a web redeploy |

## Run it locally

From `backend/`:

| Command | What it does | Cost |
| --- | --- | --- |
| `uv sync` | Install dependencies | — |
| `uv run uvicorn app.main:app --reload` | API on :8000 (live model if `.env` has a key) | Credits per analysis |
| `MODEL_BACKEND=fake uv run uvicorn app.main:app` | API on the fake model | Free |
| `uv run pytest` | 165 tests, fake model only | Free |
| `uv run python -m scripts.check_setup` | Pings both models, reads rate limits, tests JSON mode and Tavily | A few cents |
| `uv run python -m scripts.eval` | Phase 1 gate: 15 fixtures on the real models | About $0.10 |
| `uv run python -m scripts.rehearse` | Phase 2 gate: 200 fake jobs, live queue view | Free |
| `uv run python -m scripts.kill_test` | Phase 3 gate: real Greenhouse postings, fake model, kill and resume | Free |
| `uv run python -m scripts.record_sample --api URL` | Record the web app's sample run (4 examples, a 200-posting batch, a metrics timeline) into `web/public/sample/` | Free on the fake model; about $1 to $2 live |

From `web/`: `npm install`, then `npm run dev` (Vite on :5173, proxying `/api`, `/health` and `/metrics` to :8000). `npm run build` and `npm run lint` (oxlint) must both be clean.

## Code map

| Path | Role |
| --- | --- |
| `backend/app/main.py` | FastAPI app: lifespan (build engine, replay log, resume batches), all endpoints |
| `backend/app/config.py` | Settings from env and `.env`; blank values keep defaults |
| `backend/app/schemas.py` | `Status`, `SignalType`, `Label`, `Signal`, `Analysis`, `Verdict` |
| `backend/app/normalize.py` | HTML to text keeping line breaks; `quote_in_text` for quote checks |
| `backend/app/analyzer.py` | Nemotron cascade: Nano finds sentences, Ultra classifies; quotes verified; a reply with no JSON is retried with reasoning off; repeated quotes merged. `PROMPT_VERSION = "p1"` |
| `backend/app/rules.py` | The verdict rules table as code (`decide(analysis, status)`) |
| `backend/app/llm.py` | `TokenFactoryModel` (AsyncOpenAI, JSON mode, temperature 0); checks the budget before every call and records token cost |
| `backend/app/budget.py` | `Budget` (dollars per UTC day, read from `cost_micro_usd`) and `HourlyLimit` (sliding hour, all callers) |
| `backend/app/company_context.py` | Tavily lookup for Unclear verdicts |
| `backend/app/greenhouse.py` | Greenhouse fetch, US filter, `PRESET_COMPANIES` (20 boards); `fetch_job` and `JOB_URL` for a single pasted link |
| `backend/app/posting_link.py` | Reads a posting from a link: Greenhouse through its API, anything else through Tavily Extract (advanced). Rewrites search-page links (Wellfound `job_listing_slug`, LinkedIn `currentJobId`) to the job's own page. Refuses sign-in walls (under 300 characters) and anything that doesn't look like one posting (over 40,000 characters, or fewer than 4 of 17 posting words) |
| `backend/app/batches.py` | `BatchRunner`: one fetcher per company, resume from the log, `view()` |
| `backend/app/fixtures.py` | 15 invented postings (`backend/fixtures/postings.json`), `numbered_postings` |
| `backend/app/engine/queue.py` | Hand-written `BoundedQueue` on two `asyncio.Condition`s |
| `backend/app/engine/pool.py` | `WorkerPool`, graceful drain |
| `backend/app/engine/guarded.py` | Global semaphore plus retries with full-jitter backoff on 429/5xx |
| `backend/app/engine/ring.py` | Consistent-hash ring, 64 virtual nodes per shard |
| `backend/app/engine/cache.py` | Sharded LRU with single-flight; key = prompt version + model IDs + content hash |
| `backend/app/engine/log.py` | `LogStore` interface, `JsonlLogStore`, `GroupCommitLog` (~100 ms group commit, fsync) |
| `backend/app/engine/engine.py` | 4 shards of queue + workers, cache before the model, done only once logged, replay on start |
| `backend/app/engine/metrics.py` | Counters, gauges, windowed p50/p95 histograms |
| `backend/app/engine/fake_model.py` | Keyword `FakeModel` with set latency, 429 and 503 rates |
| `backend/scripts/record_sample.py` | Records the sample run the web app shows when the engine is asleep or off |
| `web/src/App.tsx` | Shell: header, status picker and tabs (all kept in the URL: `?view=&status=&batch=&verdict=`), banner, footer |
| `web/src/engine.ts` | `useEngine`: probes `/health` then `/metrics`; `live`, `waking` (slow health), `no-engine` (503, no key) or `offline`, plus `liveBatches` from `/health` |
| `web/src/CheckView.tsx` | Paste box (text or a link, read into the box first), Start over button, examples, verdict card, per-status switch, Tavily panel, posting text with quotes marked |
| `web/src/BatchView.tsx` | Start a batch from the presets, poll it, filter by verdict, 50 rows at a time |
| `web/src/DashboardView.tsx` | Lazy-loaded. Stat tiles, shard meters, three single-series Recharts lines; SSE live, or the sample replayed |
| `web/src/lib.ts`, `components.tsx`, `api.ts` | Status names, label styles, URL state, quote highlighting; shared UI; API types and sample loading |
| `web/public/sample/` | The recorded live sample run (Oct 27): 4 examples with Tavily, 200 real postings, a metrics timeline compacted to every third second |
| `render.yaml` | Render blueprint for both services |
| `FEEDBACK.md` | Running feedback on Token Factory and NVIDIA tools, for the form |

## API

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Liveness, plus `live_batches` (false on the hosted demo) |
| `GET /metrics` | Counters, gauges (per shard too), histograms, recovery stats |
| `GET /api/ping-model` | Phase 0 check against Nano (counts toward the hourly limit) |
| `POST /api/analyze` `{text, status}` | Analysis, the verdict for `status`, `verdicts` for all four statuses, the normalized `text`, company context (Tavily, only when Unclear). 429 when the hourly limit or the day's budget is used up; a cached posting is still answered after the budget is spent |
| `POST /api/read-link` `{url}` | A posting's normalized text from its link, for the paste box; 422 with a reason when the page isn't a readable posting. Counts toward the hourly limit |
| `GET /api/company-context?company=` | Tavily context on demand, when the web app switches to a status that is Unclear. Results are kept per company. Counts toward the hourly limit |
| `GET /api/stream` | Server-sent events: a metrics snapshot twice a second |
| `POST /api/batch` `{companies, per_company, status}` | Start a batch of preset Greenhouse boards (preset companies only; 1 to 25 each). 403 when `LIVE_BATCHES=false` |
| `GET /api/batch/{id}?status=` | Progress plus a verdict per posting for any status |
| `GET /api/batches` | Batch summaries, newest first |
| `GET /api/presets` | The preset company list |
| `POST /api/rehearsal` `{jobs}` | Fake-model load test (fake backend only) |

Without a key and with `MODEL_BACKEND=live`, every engine endpoint returns 503 with a message saying what to set.

## Decisions and deviations from the plan

| Topic | What was done | Why |
| --- | --- | --- |
| Models | Nano `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, Ultra `nvidia/Nemotron-3-Ultra-550b-a55b`; `json_object` mode on both | Both honour JSON mode though the catalog doesn't tag it |
| Concurrency | `model_concurrency = 8` | Measured limits: Nano 100 RPM / 800K TPM, Ultra 300 RPM / 200K TPM |
| Retries | GuardedModel owns them (SDK retries off); 3 tries, slot released during backoff | Token Factory had intermittent 503s on Oct 24 |
| Shards | 4 shards; settings `workers` and `queue_capacity` are totals split across shards | Equal total workers makes the 1-shard vs 4-shard benchmark fair |
| Rehearsal gate | Passes when at least one shard fills | Jobs spread randomly; not every shard fills in every run |
| Cache lock | `threading.Lock` per shard, critical sections never await | Correct under asyncio, and safe for the threaded stretch goal |
| Job IDs | Batch jobs are `{batch_id}:{source}` | Makes resume idempotent |
| Resume | Unfinished batches re-fetch their boards; finished job IDs come back from the log with no model call | The log never stores posting text |
| Log location | `backend/data/sponsorlens.jsonl` (`LOG_PATH`), gitignored | Render's free disk is wiped on sleep; recovery is shown locally |
| Batch companies | Only from `PRESET_COMPANIES` | Repeat runs are mostly cache hits; keeps spend bounded |
| US filter | Location and office strings; `DE` and `IN` left out of state codes | They collide with Germany and India |
| Render naming | API service is `sponsorlens`, not `sponsorlens-api` | Blueprint creation of `sponsorlens-api` failed; created by hand |
| Status switching | `/api/analyze` returns all four verdicts; the web app switches locally | No second request, and no rules logic duplicated in the browser |
| Token counts | Models report `tokens_in` / `tokens_out` to the shared metrics (FakeModel estimates 4 characters per token) | Feeds tokens per second on the dashboard |
| Sample mode | Recorded JSON shipped with the static site; shown whenever the engine is not live | The hosted API sleeps and has no key until Phase 5 |
| Token cap | `max_tokens` 8192 (was 4096) | Nano's reasoning took 3,066 tokens on a long SpaceX posting and once ran out before writing JSON |
| JSON retries | An empty or JSON-less reply is asked again unchanged, a malformed one is shown its error; up to two retries | Failures were random, not tied to a posting; showing an empty reply back didn't help |
| Nano reasoning | Left on | With reasoning off, Nano was 3× faster but copied an irrelevant sentence (a home-office budget) |
| Tavily sources | Only sources that name the company are kept | For an invented company the search returned generic sponsor lists, which would have misled |
| Spending | Measured, not guessed: `cost_micro_usd` counter from catalog prices | Plan for the $25 alone |
| Spending limits | Three layers. `Budget` refuses any model call once the UTC day's spend reaches `DAILY_BUDGET_USD` (default $1; $0.50 on Render), checked inside `TokenFactoryModel` so batches, retries and single checks all stop. `HourlyLimit` caps `/api/analyze`, `/api/company-context` and `/api/ping-model` together (`HOURLY_REQUESTS`, default 60; 30 on Render). `LIVE_BATCHES=false` on Render, where the batch and engine tabs replay the recorded run | Render's free disk is wiped on sleep, so the day's count resets on every restart. A restart needs 15 idle minutes, and the hourly limit slows spending between restarts. A typical check costs about $0.0015, so $0.50 is about 300 checks a day. Worst case, someone scripting long postings through every wake could still spend more than $0.50 a day; the owner watches the balance and can remove the key on Render at any time |
| Links | Greenhouse links use its Job Board API; other links go through Tavily Extract (basic depth, text format) | The server never fetches arbitrary URLs itself (no SSRF surface), and it adds a second Tavily use. Checked Oct 28: Greenhouse, Stripe's own careers page and Lever all read about 4,600 characters of clean text |
| Wrong pages | A linked page must look like one posting (4+ posting words, under 40,000 characters) or it gets no verdict | Oct 28: a Wellfound search link read a list of other startups' jobs and got Clear, while the real job needed a Top Secret clearance. Measured: real postings had 6 to 13 of the words, a search page, a jobs list and a home page had 1 to 3. The check is a heuristic; pasted text is not checked |
| Link reading depth | Tavily Extract `advanced` | On Wellfound, `basic` dropped the "Visa Sponsorship: Not Available" label and every bullet list. Costs twice the Tavily credits |
| No-JSON fallback | A reply with no JSON is asked again with reasoning off (`chat_template_kwargs.enable_thinking=false`), not repeated | Oct 28 on the hosted demo: a noisy page made Nano use all 8,192 tokens reasoning three times (about 90 s) and fail. Without reasoning Nano answered in 1.4 s with the right sentence. Reasoning stays on for the first try because it reads more carefully |
| Error messages | People see what to do ("paste just the job description", "try again in a minute"); the raw error goes to the server log | The raw "ValueError: no JSON object in reply" meant nothing to a tester |
| Start over | The reset button is called Start over, not Clear | "Clear" is also a verdict; a test caught the clash |
| Scope | Work authorization only; broader checks (remote or location limits, degree requirements) go in the README as the roadmap | Suggested by the Phase 4 tester; too big for the days left, and a narrow tool that quotes its evidence is easier to trust |
| Colors | Data-viz reference palette: status colors good, warning and critical for Clear, Unclear and Blocked, always with an icon and label; one blue for series | Colorblind-safe and consistent in light and dark |

## Live measurements (Oct 27, 200 real Greenhouse postings, 20 companies)

| Measure | Value |
| --- | --- |
| Cost | $0.30 for 200 postings (303 model calls; 348K tokens in, 474K out, mostly reasoning) |
| Model latency | p50 6.4 s, p95 79 s, max 101 s (the long tail is reasoning) |
| Failures | 3 of 200 with "no JSON object in reply", before the retry fix |
| Verdicts, H-1B or OPT | 10 Clear, 24 Blocked, 163 Unclear (most postings say nothing) |
| Verdicts, EAD / green card | 172 / 191 Clear |
| Wall time | About 12.5 minutes at 8 concurrent model calls |

## Open items and owner actions

- [x] Tavily key in `.env` (free plan)
- [x] Temporary Render API key deleted Oct 28 (Render and `.env`)
- [x] Builder Program credits claimed Oct 28: Nebius $25, Tavily $25, LangSmith $100 (key in `.env`)
- [ ] Film the gate clips for the video: eval, rehearse, kill_test, and the web app waking from sleep
- [ ] Phase 5: ask on the Nebius Discord whether a usage cap and a sleeping demo are acceptable
- [ ] `docs/build-plan.md` still opens with a line naming the doc it was exported from; reword before submission if wanted

## Next steps

1. Phase 5: deploy the link reader and Start over button (pushed Oct 28), then check a link on the hosted site.
2. Phase 5: phone check over cellular: a pasted posting gets a live verdict, the batch tab shows the recording. The owner deletes the temporary Render API key (`RENDER_API_KEY` in `.env` and in Render's account settings).
3. Benchmark (`scripts/bench.py`): 1 vs 8 workers, cold vs warm cache, 1 vs 4 shards on FakeModel with latency drawn from the live measurements above, plus the live run as the real-world row. Results in `docs/bench.md`.
