# Engine benchmark

What the engine's parts are worth, measured on Oct 28, 2026. Reproduce from `backend/` with `uv run python -m scripts.bench` (about 10 minutes, no cost).

## How it was measured

The benchmark runs the real engine (queues, workers, cache, log, shards) on the fake model, which gives keyword-based answers instead of calling Nemotron. To make the timing real, every fake model call waits for a time drawn from the latency of the live run on Oct 27: 200 real Greenhouse postings through Nemotron on Token Factory, where a call took 6.4 s at the median, 79 s at the 95th percentile and 101 s at most. The long tail is Nemotron's reasoning.

The waits are run 100 times faster than real time, and every time below is scaled back up. Because a few calls take ten times the median, each setting was run with three random seeds and the median is reported.

Two differences from the live run: the fake model sends almost every posting on to the second model (387 calls for 200 postings, against 303 live), and the cost column uses the live run's measured average of $0.0015 per posting rather than measuring tokens.

**The simulation is close to reality.** The live run used the default layout, 8 workers in 4 shards, and took about 12.5 minutes. The same layout in the simulation takes 17.4 minutes, but it makes 28% more model calls; scaled to the live run's 303 calls, that is about 13.6 minutes.

## Workers

200 postings from 20 companies, one shard, with the model concurrency cap equal to the number of workers.

| Workers | Wall time for 200 postings | Postings per minute | Time to verdict p50 / p95 |
| --- | --- | --- | --- |
| 1 | 106.0 min | 2 | 25.6 min / 31.9 min |
| 2 | 52.3 min | 4 | 12.4 min / 16.1 min |
| 4 | 25.8 min | 8 | 5.9 min / 9.5 min |
| 8 | 13.2 min | 15 | 3.0 min / 5.2 min |
| 16 | 7.2 min | 28 | 1.5 min / 3.1 min |

Throughput scales almost linearly: the work is waiting on the model, so more concurrent calls means proportionally more done. The live engine stays at 8 because of Token Factory's measured rate limits (Ultra allows 200,000 tokens a minute, and a reasoning call can use several thousand); at 8 the live run saw no rate-limit errors. Time to verdict counts from the moment a whole batch is submitted, so with one worker the median posting waits behind about a hundred others.

## Cache

| Run (8 workers) | Wall time | Model calls | Model cost at live prices |
| --- | --- | --- | --- |
| 200 postings, cache cold | 13.2 min | 387 | $0.30 |
| The same 200 again, cache warm | 0.2 s | 0 | $0.00 |
| 200 submissions of 20 distinct postings, all at once | 7.1 min | 39 | $0.03; 82 submissions waited on a call already in flight |

A repeated posting costs nothing and returns at once. The cache key is the posting's content plus the prompt version and the model IDs, so a changed prompt or model never serves a stale answer.

The last row is single-flight: when ten copies of a posting arrive together, one model call is made and the other copies wait for it instead of each calling the model. 200 submissions made 39 calls (20 for the first model and 19 for the second), not about 390. The wall time is set by the slowest of those few calls, which is why it varies between seeds (6 to 13 minutes).

## Shards

Each shard has its own queue and its own workers; postings are routed to a shard by company, through a consistent-hash ring. The total is always 8 workers: one shard of 8, or four shards of 2.

| Load | Shards (8 workers in all) | Ordinary postings: time to verdict p50 / p95 | Wall time |
| --- | --- | --- | --- |
| 20 companies, 10 postings each | 1 | 3.0 min / 5.2 min | 13.3 min |
| 20 companies, 10 postings each | 4 | 3.4 min / 5.8 min | 17.4 min |
| The same, plus one company with 60 long postings | 1 | 4.6 min / 7.9 min | 24.8 min |
| The same, plus one company with 60 long postings | 4 | 3.6 min / 6.3 min | 42.4 min |

"Long postings" take four times as long per model call, like the long postings whose reasoning ran past 3,000 tokens in the live run.

**Shards trade throughput for isolation, and this benchmark shows both sides.**

- **Isolation works.** When one company floods the engine with slow postings, everyone else's postings get their verdicts about 20% sooner on four shards (median 3.6 min instead of 4.6; 95th percentile 6.3 min instead of 7.9). On one shard, the flood takes all eight workers and everyone waits behind it; on four, it can only ever use its own shard's two.
- **Throughput costs.** On an even load, four shards are about 30% slower (17.4 min against 13.3). Workers can't help another shard, and 20 companies don't hash evenly onto 4 shards, so some shards finish early and sit idle while others still have work. With the flood, the whole batch takes 70% longer, because the flooding company is held to two workers.

In one process, a single shared pool is faster. The shards are there to model a multi-node design, where each node owns its queue, and to cap how much of the engine one company can take. A production version would keep the isolation and win back the throughput by letting idle workers take work from a busy shard. The shard count is a setting (`SHARDS`), so it can be set to 1 where throughput matters more.

## The live run, for reference

Oct 27, 200 real postings from 20 Greenhouse boards, Nemotron Nano then Ultra on Token Factory, 8 workers in 4 shards:

| Measure | Value |
| --- | --- |
| Wall time | About 12.5 minutes |
| Model calls | 303 (348,000 tokens in, 474,000 out, mostly reasoning) |
| Cost | $0.30 |
| Model latency | p50 6.4 s, p95 79 s, max 101 s |
| Failures | 3 of 200 with no JSON in the reply, since fixed by retrying without reasoning |
