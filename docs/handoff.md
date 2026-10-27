# SponsorLens handoff

Everything someone needs to pick this project up cold: what is done, what is live, how to run it, how the code is laid out, what was decided and why, and what comes next. Updated at every phase step; the date on each section says when it was last true.

The full plan, with its phase gates, lives in [build-plan.md](build-plan.md). This doc records where reality has got to against it.

## At a glance (Oct 27, 2026)

| | |
| --- | --- |
| What it is | Reads a US job posting and gives a verdict (Clear, Unclear, Blocked) per work-authorization status (EAD, OPT, H-1B, green card), quoting the posting as evidence. Backed by a hand-built asyncio engine |
| Hackathon | Nebius x NVIDIA Global AI Hackathon, solo entry, Best Apps and Agents track plus the Tavily prize |
| Deadline | **Fri Oct 30, 2026, 10:00am PDT.** Plan: submit Thu Oct 29 evening |
| Repo | https://github.com/him-agni/sponsorlens (public, MIT, branch `main`) |
| Web app | https://sponsorlens-web.onrender.com (Render static site) |
| API | https://sponsorlens.onrender.com (Render free web service; `/health` works) |
| Schedule | About one day behind the plan. Phases 0 to 3 done; Phase 4 built, its gate (a new user reads a verdict unaided) still to run |

## Phase status

| Phase | Planned | State | Gate result |
| --- | --- | --- | --- |
| P0 Setup, first model call | Fri Oct 23 | Done | `/api/ping-model` returned a Nemotron reply |
| P1 Verdict for one posting | Sat Oct 24 | Done | Eval 15/15 for all four statuses, 0 unverified quotes (prompt `p1`) |
| P2 Engine core, first deploy | Sun Oct 25 | Done Oct 27 | Rehearsal fills and drains the queues; web app reaches the API on Render ("Engine status: ok", 389 ms). Still to film: `/health` after the API wakes from sleep |
| P3 Intake, shards, cache, log | Mon Oct 26 | Done Oct 27 | `scripts/kill_test.py`: killed mid-batch at 82/200, restarted, 82 returned from the log, 117 analysed, 1 cache hit, 0 postings finished twice |
| P4 Web app and dashboard | Tue Oct 27 | Built Oct 27 | Checked in light, dark, desktop and 390 px phone width, live and sample mode, no console errors. Live sample recorded and committed. Still to do: the owner's husband checks the deployed site remotely and explains a verdict back unaided |
| P5 Deploy, limits, benchmark | Wed Oct 28 | Not started | — |
| P6 Video, README, submit | Thu Oct 29 | Not started | — |

## Working rules

These come from the owner and apply to every change.

- **Authorship.** The owner (GitHub `him-agni`) is the sole author. Never add `Co-Authored-By` trailers or any AI attribution to commits, PRs or files. Commits use the noreply email `100171053+him-agni@users.noreply.github.com`, set in the repo's local git config.
- **Commits.** Small commits, one per component, prefixed with the phase (`Phase 3: ...`), each passing the tests on its own. Never one commit for a whole phase.
- **Push** only when the owner says so. Before pushing, check the unpushed commits for attribution and for keys.
- **Secrets.** API keys live only in the repo-root `.env` (gitignored). Never print them, paste them or commit them.
- **Spending.** The hosted API has no `NEBIUS_API_KEY` until Phase 5 adds a daily budget, so the public demo can't spend credits. Engine work uses `MODEL_BACKEND=fake`.

## Accounts and credits

| Item | State |
| --- | --- |
| Nebius Token Factory | Key in `.env`. $25 promo credit arrived Oct 24. The Builder Program credit never arrived; **the plan assumes only the $25.** Spent so far: well under $1 (eval, a 10-posting probe, the $0.30 sample run) |
| Tavily | Free-plan key in `.env` since Oct 27 (1,000 searches a month, no card) |
| Render | Free tier, no card. Services: `sponsorlens` (API, created by hand because the blueprint's `sponsorlens-api` step failed) and `sponsorlens-web` (static site) |
| Render env vars | API: `CORS_ORIGINS=["https://sponsorlens-web.onrender.com"]`. Web: `VITE_API_URL=https://sponsorlens.onrender.com`. Vite bakes `VITE_API_URL` in at build time, so changing it needs a web redeploy |

## Run it locally

From `backend/`:

| Command | What it does | Cost |
| --- | --- | --- |
| `uv sync` | Install dependencies | — |
| `uv run uvicorn app.main:app --reload` | API on :8000 (live model if `.env` has a key) | Credits per analysis |
| `MODEL_BACKEND=fake uv run uvicorn app.main:app` | API on the fake model | Free |
| `uv run pytest` | 140 tests, fake model only | Free |
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
| `backend/app/analyzer.py` | Nemotron cascade: Nano finds sentences, Ultra classifies; quotes verified; one retry. `PROMPT_VERSION = "p1"` |
| `backend/app/rules.py` | The verdict rules table as code (`decide(analysis, status)`) |
| `backend/app/llm.py` | `TokenFactoryModel` (AsyncOpenAI, JSON mode, temperature 0) |
| `backend/app/company_context.py` | Tavily lookup for Unclear verdicts |
| `backend/app/greenhouse.py` | Greenhouse fetch, US filter, `PRESET_COMPANIES` (20 boards) |
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
| `web/src/engine.ts` | `useEngine`: probes `/health` then `/metrics`; `live`, `waking` (slow health), `no-engine` (503, no key) or `offline` |
| `web/src/CheckView.tsx` | Paste box, examples, verdict card, per-status switch, Tavily panel, posting text with quotes marked |
| `web/src/BatchView.tsx` | Start a batch from the presets, poll it, filter by verdict, 50 rows at a time |
| `web/src/DashboardView.tsx` | Lazy-loaded. Stat tiles, shard meters, three single-series Recharts lines; SSE live, or the sample replayed |
| `web/src/lib.ts`, `components.tsx`, `api.ts` | Status names, label styles, URL state, quote highlighting; shared UI; API types and sample loading |
| `web/public/sample/` | The recorded live sample run (Oct 27): 4 examples with Tavily, 200 real postings, a metrics timeline compacted to every third second |
| `render.yaml` | Render blueprint for both services |
| `FEEDBACK.md` | Running feedback on Token Factory and NVIDIA tools, for the form |

## API

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Liveness |
| `GET /metrics` | Counters, gauges (per shard too), histograms, recovery stats |
| `GET /api/ping-model` | Phase 0 check against Nano |
| `POST /api/analyze` `{text, status}` | Analysis, the verdict for `status`, `verdicts` for all four statuses, the normalized `text`, company context (Tavily, only when Unclear) |
| `GET /api/company-context?company=` | Tavily context on demand, when the web app switches to a status that is Unclear. Results are kept per company |
| `GET /api/stream` | Server-sent events: a metrics snapshot twice a second |
| `POST /api/batch` `{companies, per_company, status}` | Start a batch of preset Greenhouse boards (preset companies only; 1 to 25 each) |
| `GET /api/batch/{id}?status=` | Progress plus a verdict per posting for any status |
| `GET /api/batches` | Batch summaries, newest first |
| `GET /api/presets` | The preset company list |
| `POST /api/rehearsal` `{jobs}` | Fake-model load test (fake backend only) |

Without a key and with `MODEL_BACKEND=live`, every engine endpoint returns 503 with a message saying what to set. That is the hosted API's state today.

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
- [x] Builder Program credit: not arrived; planning without it
- [ ] Film the gate clips for the video: eval, rehearse, kill_test, and the web app waking from sleep
- [ ] Phase 5: ask on the Nebius Discord whether a usage cap and a sleeping demo are acceptable
- [ ] `docs/build-plan.md` still opens with a line naming the doc it was exported from; reword before submission if wanted

## Next steps

1. Phase 4 gate: the owner's husband checks the deployed site from his phone and explains a verdict back (message and pass criteria were given to the owner).
2. Phase 5, budget first: Render's free disk is wiped on sleep, so a spend counter there resets on every wake. Plan: on the hosted API only single-posting checks run live, under a dollar cap per process plus a per-day cap; batches on the hosted site show the recorded run. Then keys on Render, deploy, phone check over cellular.
3. Benchmark (`scripts/bench.py`): 1 vs 8 workers, cold vs warm cache, 1 vs 4 shards on FakeModel with latency drawn from the live measurements above, plus the live run as the real-world row. Results in `docs/bench.md`.
