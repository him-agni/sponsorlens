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
| Schedule | About one day behind the plan. Phases 0 to 5 done; Phase 5 spending limits live on Render Oct 28 |

## Phase status

| Phase | Planned | State | Gate result |
| --- | --- | --- | --- |
| P0 Setup, first model call | Fri Oct 23 | Done | `/api/ping-model` returned a Nemotron reply |
| P1 Verdict for one posting | Sat Oct 24 | Done | Eval 15/15 for all four statuses, 0 unverified quotes (prompt `p1`) |
| P2 Engine core, first deploy | Sun Oct 25 | Done Oct 27 | Rehearsal fills and drains the queues; web app reaches the API on Render ("Engine status: ok", 389 ms). Still to film: `/health` after the API wakes from sleep |
| P3 Intake, shards, cache, log | Mon Oct 26 | Done Oct 27 | `scripts/kill_test.py`: killed mid-batch at 82/200, restarted, 82 returned from the log, 117 analysed, 1 cache hit, 0 postings finished twice |
| P4 Web app and dashboard | Tue Oct 27 | Done Oct 28 | Checked in light, dark, desktop and 390 px phone width, live and sample mode, no console errors. Gate passed Oct 28: a new user (the owner's husband) used the deployed site on his phone and explained a verdict back unaided. His requests: a clear button and pasting a link (both built), and a wider scope (roadmap) |
| P5 Deploy, limits, benchmark | Wed Oct 28 | Done | Done Oct 28. Limits deployed and keys on Render: `/health` shows `live_batches: false`, `/metrics` shows a $0.50 budget, `POST /api/batch` is 403, a live check returned Blocked with the right quote for $0.0024. Phone check on Wi-Fi (cellular unavailable; the site is public either way). Tester fixes shipped: Start over, links, wrong-page check, no-JSON fallback. Benchmark in `docs/bench.md` |
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
| Render env vars | API: `CORS_ORIGINS=["https://sponsorlens-web.onrender.com"]`, `NEBIUS_API_KEY`, `TAVILY_API_KEY`, `LIVE_BATCHES=false`, `DAILY_BUDGET_USD=1`, `HOURLY_REQUESTS=60` (set Oct 28 through the Render API, raised from $0.50 and 30 by the owner the same evening for board scans; the service was made by hand, so `render.yaml` is not applied to it). A stray `VITE_API_URL` on the API service is harmless. Web: `VITE_API_URL=https://sponsorlens.onrender.com`. Vite bakes `VITE_API_URL` in at build time, so changing it needs a web redeploy |

## Run it locally

From `backend/`:

| Command | What it does | Cost |
| --- | --- | --- |
| `uv sync` | Install dependencies | — |
| `uv run uvicorn app.main:app --reload` | API on :8000 (live model if `.env` has a key) | Credits per analysis |
| `MODEL_BACKEND=fake uv run uvicorn app.main:app` | API on the fake model | Free |
| `uv run pytest` | 194 tests, fake model only; add `--cov=app --cov-report=term-missing` for coverage (99% on Oct 28) | Free |
| `uv run python -m scripts.check_setup` | Pings both models, reads rate limits, tests JSON mode and Tavily | A few cents |
| `uv run python -m scripts.eval` | Phase 1 gate: 15 fixtures on the real models | About $0.10 |
| `uv run python -m scripts.rehearse` | Phase 2 gate: 200 fake jobs, live queue view | Free |
| `uv run python -m scripts.bench` | Benchmark: workers, cache and shards on the fake model with live latencies, 3 seeds each (about 10 minutes); results in `docs/bench.md` | Free |
| `uv run python -m scripts.kill_test` | Phase 3 gate: real Greenhouse postings, fake model, kill and resume | Free |
| `uv run python -m scripts.record_sample --api URL` | Record the web app's sample run (4 examples, a 200-posting batch, a metrics timeline) into `web/public/sample/` | Free on the fake model; about $1 to $2 live |

From `web/`: `npm install`, then `npm run dev` (Vite on :5173, proxying `/api`, `/health` and `/metrics` to :8000). `npm run build` and `npm run lint` (oxlint) must both be clean. `npm test` runs 26 Vitest unit and component tests (jsdom; `src/test/network.ts` stands in for the network and serves the recorded samples). `npm run test:e2e` runs 10 Playwright tests in the installed Edge, desktop and phone: it starts the real API on the fake model (port 8000, Tavily key overridden so nothing is spent) and Vite on :5175; link reading and board scans are answered in the test so they stay offline. Test files have their own `tsconfig.test.json`.

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
| `backend/app/glance.py` | At a glance: location, work mode, experience, education, salary, job type from one Nano call with reasoning off; each fact kept only if its quote is in the posting and backs the answer; cached per posting |
| `backend/app/recent.py` | `Recent`: a small least-recently-used map for the per-process caches (company context, at a glance) |
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
| `web/src/App.tsx` | Shell: sticky header (section links, Under the hood, theme switch), the home page or the Under the hood views (`?view=engine` or `?view=batch`), footer |
| `web/src/Home.tsx` | Landing page: hero (headline with the sweeping highlight, floating rule chips, three sample verdicts), sites marquee, Check a job, Scan a board, How it works, FAQ. Sections fade up on scroll (`useReveal`) |
| `web/src/BoardScan.tsx` | Scan a Greenhouse board: link plus optional title keyword, polls the batch, results as job cards tinted by verdict with filters and Details; recorded examples (Scale AI, Anthropic, SpaceX, Robinhood) when not live |
| `web/src/engine.ts` | `useEngine`: probes `/health` then `/metrics`; `live`, `waking` (slow health), `no-engine` (503, no key) or `offline`, plus `liveBatches` from `/health` |
| `web/src/CheckView.tsx` | Paste box (text or a link, read into the box first), Start over button, examples, verdict card, per-status switch, Tavily panel, posting text with quotes marked |
| `web/src/BatchView.tsx` | Start a batch from the presets, poll it, filter by verdict, 50 rows at a time |
| `web/src/DashboardView.tsx` | Lazy-loaded. Stat tiles, shard meters, three single-series Recharts lines; SSE live, or the sample replayed |
| `web/src/lib.ts`, `components.tsx`, `api.ts` | Status names, label styles, URL state, quote highlighting; shared UI; API types and sample loading |
| `web/public/sample/` | The recorded live sample run (Oct 27): 4 examples with Tavily, 200 real postings, a metrics timeline compacted to every third second |
| `backend/scripts/bench.py` | The benchmark; `LiveLikeModel` wraps FakeModel with a lognormal latency fitted to the live run |
| `docs/bench.md` | Benchmark results and what they mean |
| `render.yaml` | Render blueprint for both services |
| `FEEDBACK.md` | Running feedback on Token Factory and NVIDIA tools, for the form |

## API

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Liveness, plus `live_batches` (false on the hosted demo) |
| `GET /metrics` | Counters, gauges (per shard too), histograms, recovery stats |
| `POST /api/analyze` `{text, status}` | Analysis, the verdict for `status`, `verdicts` for all four statuses, the normalized `text`, company context (Tavily, only when Unclear). 429 when the hourly limit or the day's budget is used up; a cached posting is still answered after the budget is spent |
| `POST /api/read-link` `{url}` | A posting's normalized text from its link, for the paste box; 422 with a reason when the page isn't a readable posting. Counts toward the hourly limit |
| `GET /api/company-context?company=` | Tavily context on demand, when the web app switches to a status that is Unclear. Results are kept per company. Counts toward the hourly limit |
| `GET /api/stream` | Server-sent events: a metrics snapshot twice a second |
| `POST /api/scan` `{url, status, keyword?}` | Scan one Greenhouse board's US jobs (titles containing the keyword, if given), at most `SCAN_LIMIT` (10). Allowed even with `LIVE_BATCHES=false`; the hourly limit is charged one request per job, and it refuses up front if the day's budget is spent. Returns `{id, company, found, scanning}`; poll `/api/batch/{id}` |
| `POST /api/batch` `{companies, per_company, status}` | Start a batch of preset Greenhouse boards (preset companies only; 1 to 25 each). 403 when `LIVE_BATCHES=false` |
| `GET /api/batch/{id}?status=` | Progress plus a verdict per posting for any status |
| `GET /api/presets` | The preset company list |

Without a key and with `MODEL_BACKEND=live`, every engine endpoint returns 503 with a message saying what to set.

## Decisions and deviations from the plan

| Topic | What was done | Why |
| --- | --- | --- |
| Models | Nano `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, Ultra `nvidia/Nemotron-3-Ultra-550b-a55b`; `json_object` mode on both | Both honour JSON mode though the catalog doesn't tag it |
| Concurrency | `model_concurrency = 8` | Measured limits: Nano 100 RPM / 800K TPM, Ultra 300 RPM / 200K TPM |
| Retries | GuardedModel owns them (SDK retries off); 3 tries, slot released during backoff | Token Factory had intermittent 503s on Oct 24 |
| Shards | 4 shards; settings `workers` and `queue_capacity` are totals split across shards | Equal total workers makes the 1-shard vs 4-shard benchmark fair. Measured: 4 shards cut other companies' wait by about 20% when one company floods the engine, but are about 30% slower on an even load, because workers can't help another shard. Kept at 4 to show isolation; `SHARDS=1` where throughput matters |
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
| End date | `LIVE_UNTIL` (default 2026-12-15, the last day of judging) is the last live day in Pacific time. From Dec 16, every endpoint that can call Token Factory or Tavily answers 503, `Budget` refuses any model call (so a batch running at midnight stops too), and `/health` reports `live: false`, which the web app shows as recordings with an "ended" banner. Render stays on the free tier | The owner must not be charged after judging. Tests turn the end date off in `tests/conftest.py` so they pass on any date |
| Spending limits | Three layers. `Budget` refuses any model call once the UTC day's spend reaches `DAILY_BUDGET_USD` (default $1, also $1 on Render), checked inside `TokenFactoryModel` so batches, retries and single checks all stop. `HourlyLimit` caps `/api/analyze`, `/api/read-link`, `/api/company-context` and `/api/scan` together (`HOURLY_REQUESTS`, default 60, also 60 on Render). `LIVE_BATCHES=false` on Render, where the batch and engine tabs replay the recorded run | Render's free disk is wiped on sleep, so the day's count resets on every restart. A restart needs 15 idle minutes, and the hourly limit slows spending between restarts. A typical check costs about $0.0015, so $0.50 is about 300 checks a day. Worst case, someone scripting long postings through every wake could still spend more than $0.50 a day; the owner watches the balance and can remove the key on Render at any time |
| Links | Greenhouse links use its Job Board API; other links go through Tavily Extract (basic depth, text format) | The server never fetches arbitrary URLs itself (no SSRF surface), and it adds a second Tavily use. Checked Oct 28: Greenhouse, Stripe's own careers page and Lever all read about 4,600 characters of clean text |
| Wrong pages | A linked page must look like one posting (4+ posting words, under 40,000 characters) or it gets no verdict | Oct 28: a Wellfound search link read a list of other startups' jobs and got Clear, while the real job needed a Top Secret clearance. Measured: real postings had 6 to 13 of the words, a search page, a jobs list and a home page had 1 to 3. The check is a heuristic; pasted text is not checked |
| Link reading depth | Tavily Extract `advanced` | On Wellfound, `basic` dropped the "Visa Sponsorship: Not Available" label and every bullet list. Costs twice the Tavily credits |
| No-JSON fallback | A reply with no JSON is asked again with reasoning off (`chat_template_kwargs.enable_thinking=false`), not repeated | Oct 28 on the hosted demo: a noisy page made Nano use all 8,192 tokens reasoning three times (about 90 s) and fail. Without reasoning Nano answered in 1.4 s with the right sentence. Reasoning stays on for the first try because it reads more carefully |
| Error messages | People see what to do ("paste just the job description", "try again in a minute"); the raw error goes to the server log | The raw "ValueError: no JSON object in reply" meant nothing to a tester |
| Second tester round (Oct 28) | Landing page redesigned after a Dribbble reference the owner chose (violet brand, Manrope, highlighted headline words, pill section labels, lavender sections, fade-up and float animations, reduced-motion respected); light/dark/auto theme switch; Engine and the 200-job run moved under "Under the hood"; FAQ and a three-step tutorial; At a glance card; board scan on the main page | The tester found the app text-heavy, didn't understand what it did, and asked for a theme switch, batch scanning and a wider scope |
| Board scans on the hosted demo | Allowed, unlike batches, but capped at 10 jobs per scan inside the daily budget | A live Databricks scan of 10 jobs took about a minute and cost about $0.04, so $0.50 a day allows about 12 scans |
| Board scan links | A Greenhouse board link, or a company's own careers page (www.databricks.com/company/careers): the site's name is tried as a board token, and kept only if Greenhouse has that board and its company name contains the token. Only Greenhouse's API is asked, never the site. `my.greenhouse.io` (Greenhouse's search across companies) needs a sign-in and gets its own message | Testers pasted careers pages and the Greenhouse search, not board links. Checked live: Databricks, Stripe (a gh_jid link), Airbnb and Figma resolve; Notion and OpenAI (not on Greenhouse) get a clear message |
| Board scan sources | Greenhouse only; Lever is a possible addition (public JSON feed); LinkedIn and Wellfound have no public feed and gate listings behind sign-in, so only single links from them | |
| Start over | The reset button is called Start over, not Clear | "Clear" is also a verdict; a test caught the clash |
| Scope | Work authorization only; broader checks (remote or location limits, degree requirements) go in the README as the roadmap | Suggested by the Phase 4 tester; too big for the days left, and a narrow tool that quotes its evidence is easier to trust |
| Security and privacy review (Oct 28) | A single check is never written to disk (only batch jobs are logged, for recovery), and a job drops its text once answered; the engine's table of every job ever submitted is gone. Removed `/api/ping-model` (spent credits, unused), `/api/rehearsal` (unused; `scripts.rehearse` covers it) and `/api/batches` (listed every visitor's scans). `/api/scan` charges the hourly limit before fetching anything; request bodies over 256 KB get 413 unread; at most 20 dashboard streams; caches and the batch list are bounded; CORS is GET and POST with Content-Type only; links from data render only if http or https; server logs name a site, never a pasted link. `npm audit` and `pip-audit` found nothing; no keys or personal email anywhere in git history | Requested by the owner before submission. Known and accepted: the hourly limit is shared by all visitors (one person can use it up; per-visitor limits would need a trusted client IP), and the daily budget resets when the free server restarts |
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

1. Phase 6, Thu Oct 29: README (what it does, live link, how to run, architecture, benchmark, roadmap with the tester's wider-scope idea), video script and shot list, finish `FEEDBACK.md`, draft the Devpost fields; the owner records the video and submits.
2. Optional, only if Phase 6 is on time: LangSmith tracing for the eval and benchmark scripts (key in `.env`; local runs only).
