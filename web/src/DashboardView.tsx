import { useEffect, useState } from 'react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { API_URL, loadSample, type SampleMetrics, type Snapshot } from './api'
import { Card } from './components'

const HISTORY = 120 // points kept: one minute of live updates at two a second

type Point = { t: number; queue: number; inFlight: number; tokensPerSecond: number }

/** Live snapshots over server-sent events, or the recorded sample replayed at its own pace.
 *  The parent remounts this view when live changes, so history starts empty for each source. */
function useSnapshots(live: boolean): Snapshot[] {
  const [history, setHistory] = useState<Snapshot[]>([])

  useEffect(() => {
    const push = (snapshot: Snapshot) => setHistory((h) => [...h.slice(-(HISTORY - 1)), snapshot])
    if (live) {
      const source = new EventSource(`${API_URL}/api/stream`)
      source.onmessage = (event) => push(JSON.parse(event.data))
      return () => source.close()
    }
    let timer: ReturnType<typeof setTimeout> | undefined
    let cancelled = false
    loadSample<SampleMetrics>('metrics')
      .then(({ snapshots }) => {
        let i = 0
        const step = () => {
          if (cancelled) return
          if (i === 0) setHistory([])
          push(snapshots[i])
          i = (i + 1) % snapshots.length
          timer = setTimeout(step, i === 0 ? 6000 : 1000) // pause on the finished state, then replay
        }
        step()
      })
      .catch(() => {})
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [live])

  return history
}

function toPoints(history: Snapshot[]): Point[] {
  return history.map((s, i) => {
    const prev = history[i - 1]
    const tokens = (x: Snapshot) => (x.counters.tokens_in ?? 0) + (x.counters.tokens_out ?? 0)
    const dt = prev ? s.uptime_s - prev.uptime_s : 0
    return {
      t: s.uptime_s,
      queue: s.gauges.queue_depth ?? 0,
      inFlight: s.gauges.model_in_flight ?? 0,
      tokensPerSecond: prev && dt > 0 ? Math.max(0, Math.round((tokens(s) - tokens(prev)) / dt)) : 0,
    }
  })
}

export default function DashboardView({ live }: { live: boolean }) {
  const history = useSnapshots(live)
  const latest = history.at(-1)
  if (!latest) {
    return (
      <Card>
        <p className="text-sm text-ink-2">Connecting to the engine…</p>
      </Card>
    )
  }

  const points = toPoints(history)
  const { counters: c, gauges: g, histograms: h } = latest
  const cacheServed = (c.cache_hits ?? 0) + (c.cache_coalesced ?? 0)
  const cacheLookups = cacheServed + (c.cache_misses ?? 0)
  const latency = h.model_latency_ms
  const seconds = (ms: number | null | undefined) => (ms == null ? '–' : `${(ms / 1000).toFixed(ms < 10_000 ? 1 : 0)} s`)
  const shards = g.shards ?? 0
  const perShardCapacity = shards ? Math.round((g.queue_capacity ?? 0) / shards) : 0
  const perShardWorkers = shards ? Math.round((g.workers_total ?? 0) / shards) : 0

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold">{live ? 'The engine, live' : 'The engine, replaying a recorded run'}</h2>
        <p className="text-sm text-muted">
          {latest.backend === 'fake' ? 'FakeModel (no credits)' : 'NVIDIA Nemotron on Nebius Token Factory'} · up{' '}
          {Math.round(latest.uptime_s)} s
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Postings done" value={c.jobs_done ?? 0} note={c.jobs_failed ? `${c.jobs_failed} failed` : undefined} />
        <Stat label="Queued" value={`${g.queue_depth ?? 0} / ${g.queue_capacity ?? 0}`} note="across all shards" />
        <Stat label="Model calls in flight" value={`${g.model_in_flight ?? 0} / ${g.model_concurrency ?? 0}`} note="capped by the rate limit" />
        <Stat label="Tokens per second" value={(points.at(-1)?.tokensPerSecond ?? 0).toLocaleString()} />
        <Stat
          label="Cache hit rate"
          value={cacheLookups ? `${Math.round((100 * cacheServed) / cacheLookups)}%` : '–'}
          note={`${cacheServed} of ${cacheLookups} postings`}
        />
        <Stat label="Model latency p50 / p95" value={`${seconds(latency?.p50)} / ${seconds(latency?.p95)}`} />
        <Stat label="Retries" value={c.retries ?? 0} note={`${c.rate_limited ?? 0} rate limited (429)`} />
        <Stat
          label="Last recovery"
          value={`${g.recovery_records ?? 0} records`}
          note={`replayed from the log in ${g.recovery_ms ?? 0} ms`}
        />
      </div>

      <Card>
        <h3 className="font-semibold">Shard queues</h3>
        <p className="mt-1 text-sm text-ink-2">
          Companies are spread over {shards} shards by consistent hashing. A full queue makes its fetchers wait: that is the
          backpressure.
        </p>
        <div className="mt-4 grid gap-3">
          {Array.from({ length: shards }, (_, i) => {
            const depth = g[`shard${i}_queue_depth`] ?? 0
            const busy = g[`shard${i}_workers_busy`] ?? 0
            return (
              <div key={i} className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1.5 text-sm sm:grid-cols-[4.5rem_1fr_auto]">
                <span className="text-ink-2">Shard {i}</span>
                <div
                  className="order-last col-span-2 h-2.5 overflow-hidden rounded-full bg-grid sm:order-none sm:col-span-1"
                  role="meter"
                  aria-label={`Shard ${i} queue`}
                  aria-valuenow={depth}
                  aria-valuemin={0}
                  aria-valuemax={perShardCapacity}
                >
                  <div
                    className="h-full rounded-full bg-accent transition-[width] duration-300"
                    style={{ width: `${perShardCapacity ? (100 * depth) / perShardCapacity : 0}%` }}
                  />
                </div>
                <span className="tabular text-ink-2">
                  {depth}/{perShardCapacity} queued · {busy}/{perShardWorkers} busy
                </span>
              </div>
            )
          })}
        </div>
      </Card>

      <div className="grid gap-6 md:grid-cols-3">
        <Trend title="Postings queued" points={points} dataKey="queue" />
        <Trend title="Model calls in flight" points={points} dataKey="inFlight" />
        <Trend title="Tokens per second" points={points} dataKey="tokensPerSecond" />
      </div>
    </div>
  )
}

function Stat({ label, value, note }: { label: string; value: string | number; note?: string }) {
  return (
    <div className="rounded-2xl border border-line bg-surface p-4">
      <p className="text-xs text-ink-2">{label}</p>
      <p className="mt-1 text-2xl font-semibold tracking-tight">{value}</p>
      {note && <p className="mt-0.5 text-xs text-muted">{note}</p>}
    </div>
  )
}

function Trend({ title, points, dataKey }: { title: string; points: Point[]; dataKey: keyof Point }) {
  return (
    <Card className="p-4">
      <h3 className="text-sm font-medium">{title}</h3>
      <div className="mt-2 h-36">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points} margin={{ top: 6, right: 6, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--color-grid)" vertical={false} />
            <XAxis dataKey="t" hide />
            <YAxis
              allowDecimals={false}
              tick={{ fill: 'var(--color-muted)', fontSize: 11 }}
              tickFormatter={(v: number) => (v >= 1000 ? `${Math.round(v / 1000)}k` : String(v))}
              stroke="var(--color-axis)"
              tickLine={false}
              width={36}
            />
            <Tooltip
              formatter={(value) => [Number(value).toLocaleString(), title]}
              labelFormatter={(t) => `${Math.round(Number(t))} s`}
              contentStyle={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-line)',
                borderRadius: 8,
                fontSize: 12,
                color: 'var(--color-ink)',
              }}
            />
            <Line type="linear" dataKey={dataKey} stroke="var(--color-accent)" strokeWidth={2} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}
