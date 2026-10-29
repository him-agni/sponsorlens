# SponsorLens

SponsorLens reads a US job posting and tells a job seeker on a work permit whether the job is open to them, quoting the exact lines in the posting as evidence. Under the hood, a hand-built concurrent pipeline (bounded queues, a worker pool, consistent-hash sharding, a single-flight cache and an append-only log) processes hundreds of postings at once, with a live metrics dashboard.

Built for the Nebius x NVIDIA Global AI Hackathon. Information only, not legal advice.

## Status

Work in progress. Setup steps, architecture, benchmarks and design notes land here as the build progresses.

## Local setup

Requirements: [uv](https://docs.astral.sh/uv/) and Node.js 20 or newer.

```bash
cp .env.example .env          # then fill in the keys
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

Check the setup (both models, rate limits, JSON mode and Tavily):

```bash
uv run python -m scripts.check_setup
```

Tests use a fake model and spend no credits. The eval runs 15 invented postings through the real models and scores the verdicts:

```bash
uv run pytest
uv run python -m scripts.eval
```

The LangSmith experiments score the verdicts on 27 invented postings, 12 of them hard cases, and compare model setups side by side. The app's setup got all 27 right, with every quote found in the posting. The [LangSmith dashboard is public](https://smith.langchain.com/public/95e912e9-08e0-40b1-b9ed-51ef301aaeed/d), with every experiment and trace. The findings are in [docs/accuracy.md](docs/accuracy.md), each posting's result in [docs/accuracy-by-posting.md](docs/accuracy-by-posting.md), and the raw results in [backend/results/](backend/results/).

```bash
uv run python -m scripts.experiment --setup cascade nano-only ultra-only cascade-no-reasoning
```

The web app has unit and component tests (Vitest) and end-to-end tests (Playwright, in the installed Microsoft Edge, against the API on the fake model). From `web/`:

```bash
npm test
npm run test:e2e
```

Rehearse a 200-posting batch on a fake model and watch the queue fill, hold at capacity and drain. It costs nothing:

```bash
uv run python -m scripts.rehearse
```

To run the whole API without a key, set `MODEL_BACKEND=fake`. `GET /metrics` shows queue depth, busy workers, retries and latency percentiles.

### Batches of real postings

`POST /api/batch` with `{"companies": [...], "per_company": 10, "status": "h1b"}` fetches US postings from the preset Greenhouse boards (`GET /api/presets`), one fetcher per company, and runs them through the engine. `GET /api/batch/{id}?status=opt` returns progress and a verdict per posting for any status, without another model call.

Every finished posting is written to an append-only log (`backend/data/sponsorlens.jsonl`, set by `LOG_PATH`) before it counts as done. On startup the log is replayed: the cache is refilled and unfinished batches resume from their sources. To see it, kill the server mid-batch and restart it. This script does that on the fake model, so it costs nothing:

```bash
uv run python -m scripts.kill_test
```

It passes when the batch finishes and no posting finished before the kill is sent to the model again.

### Job data

Batches read the [Greenhouse Job Board API](https://docs.greenhouse.io/job-board.html), whose GET endpoints are public ("authentication is not required for any GET endpoints"); its documentation states no separate terms or rate limits. SponsorLens reads only published jobs, fetches each board once per batch, keeps posting text in memory only while analyzing it, never stores or republishes it (the log holds sources, titles and the quoted signals), and links every verdict to the original posting.

```bash
cd web
npm install
npm run dev
```

## Deploy

`render.yaml` deploys the API as a Render free web service and the web app as a Render static site, for $0. In Render, choose New → Blueprint and pick this repo, then enter `NEBIUS_API_KEY` and `TAVILY_API_KEY` when asked. The free service sleeps when idle and takes about a minute to wake.

## Where Nebius and NVIDIA are used

Every analysis calls NVIDIA Nemotron models through Nebius Token Factory's OpenAI-compatible API (`backend/app/llm.py`). Details to follow.

## License

MIT
