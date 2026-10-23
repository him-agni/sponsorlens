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

Check the model connection at http://localhost:8000/api/ping-model.

```bash
cd web
npm install
npm run dev
```

## Where Nebius and NVIDIA are used

Every analysis calls NVIDIA Nemotron models through Nebius Token Factory's OpenAI-compatible API (`backend/app/llm.py`). Details to follow.

## License

MIT
