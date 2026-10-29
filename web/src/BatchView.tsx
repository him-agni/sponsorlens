import { useEffect, useState } from 'react'
import { api, loadSample, type BatchRow, type BatchView as View, type Label, type SampleBatch, type Status } from './api'
import { Card, Spinner, VerdictBadge } from './components'
import { SIGNAL_NAMES, labelName, safeHref, useUrlParam } from './lib'

type Props = { status: Status; live: boolean; engineLive: boolean }
const FILTERS = ['all', 'clear', 'unclear', 'blocked'] as const
const PAGE = 50
type Filter = (typeof FILTERS)[number]

export function BatchView({ status, live, engineLive }: Props) {
  const [batchId, setBatchId] = useUrlParam<string>('batch', '')
  const [filter, setFilter] = useUrlParam<Filter>('verdict', 'all', FILTERS)
  const [fetched, setView] = useState<View | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Live: poll the batch once a second until it finishes. Otherwise: the recorded sample batch.
  useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | undefined
    if (!live) {
      loadSample<SampleBatch>('batch')
        .then((sample) => !cancelled && setView(sample.views[status]))
        .catch(() => !cancelled && setView(null))
    } else if (batchId) {
      const poll = async () => {
        try {
          const next = await api<View>(`/api/batch/${batchId}?status=${status}`)
          if (cancelled) return
          setView(next)
          setError(null)
          if (!next.finished) timer = setTimeout(poll, 1000)
        } catch (e) {
          if (!cancelled) setError(e instanceof Error ? e.message : String(e))
        }
      }
      poll()
    }
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [live, batchId, status])

  // Live with no batch picked shows only the controls.
  const view = live && !batchId ? null : fetched
  const rows = view?.items.filter((row) => filter === 'all' || row.verdict?.label === filter) ?? []
  const [shown, setShown] = useState(PAGE)

  return (
    <div className="grid grid-cols-1 gap-6">
      <BatchControls live={live} engineLive={engineLive} status={status} onStarted={setBatchId} />
      {error && <p className="text-sm text-critical-ink">{error}</p>}
      {view && (
        <>
          <Summary view={view} filter={filter} onFilter={setFilter} />
          <Card className="p-0">
            <ul className="divide-y divide-line">
              {rows.slice(0, shown).map((row) => (
                <Row key={row.job_id} row={row} />
              ))}
              {rows.length === 0 && <li className="p-5 text-sm text-ink-2">No postings match this filter yet.</li>}
            </ul>
            {rows.length > shown && (
              <button
                onClick={() => setShown((n) => n + PAGE)}
                className="w-full border-t border-line px-4 py-3 text-sm font-medium text-accent hover:bg-line"
              >
                Show more ({rows.length - shown} left)
              </button>
            )}
          </Card>
        </>
      )}
    </div>
  )
}

function BatchControls({
  live,
  engineLive,
  status,
  onStarted,
}: {
  live: boolean
  engineLive: boolean
  status: Status
  onStarted: (id: string) => void
}) {
  const [presets, setPresets] = useState<string[]>([])
  const [chosen, setChosen] = useState<Set<string>>(new Set())
  const [perCompany, setPerCompany] = useState(10)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!live) return
    api<{ companies: string[] }>('/api/presets')
      .then(({ companies }) => {
        setPresets(companies)
        setChosen(new Set(companies))
      })
      .catch(() => setPresets([]))
  }, [live])

  async function start() {
    setStarting(true)
    setError(null)
    try {
      const { id } = await api<{ id: string }>('/api/batch', {
        method: 'POST',
        body: JSON.stringify({ companies: presets.filter((c) => chosen.has(c)), per_company: perCompany, status }),
      })
      onStarted(id)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setStarting(false)
    }
  }

  const toggle = (company: string) =>
    setChosen((current) => {
      const next = new Set(current)
      if (next.has(company)) next.delete(company)
      else next.add(company)
      return next
    })

  return (
    <Card>
      <h2 className="font-semibold">Scan many real jobs at once</h2>
      <p className="mt-1 text-sm text-ink-2">
        Pulls current US openings from 20 companies' public job boards and checks every one.
      </p>
      {live ? (
        <>
          <div className="mt-4 flex flex-wrap gap-1.5">
            {presets.map((company) => (
              <button
                key={company}
                onClick={() => toggle(company)}
                aria-pressed={chosen.has(company)}
                className={`rounded-full border px-2.5 py-0.5 text-sm ${
                  chosen.has(company) ? 'border-ink bg-ink text-page' : 'border-line text-ink-2 hover:bg-line'
                }`}
              >
                {company}
              </button>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <label className="text-sm text-ink-2">
              Postings per company{' '}
              <select
                value={perCompany}
                onChange={(e) => setPerCompany(Number(e.target.value))}
                className="ml-1 rounded-md border border-line bg-page px-2 py-1 text-ink"
              >
                {[5, 10, 25].map((n) => (
                  <option key={n}>{n}</option>
                ))}
              </select>
            </label>
            <button
              onClick={start}
              disabled={starting || chosen.size === 0}
              className="inline-flex items-center gap-2 rounded-lg bg-ink px-4 py-2 text-sm font-medium text-page disabled:opacity-40"
            >
              {starting && <Spinner />}
              Run {chosen.size * perCompany} postings
            </button>
          </div>
          {error && <p className="mt-3 text-sm text-critical-ink">{error}</p>}
        </>
      ) : (
        <p className="mt-3 text-sm text-muted">
          {engineLive
            ? 'Below is a scan of 200 real jobs we ran live on Oct 27. Scans are off on this public demo to save model credits; run SponsorLens yourself to start one.'
            : 'Below is a scan of 200 real jobs we ran live on Oct 27.'}
        </p>
      )}
    </Card>
  )
}

function Summary({ view, filter, onFilter }: { view: View; filter: Filter; onFilter: (f: Filter) => void }) {
  const done = view.progress.done ?? 0
  const failed = view.progress.failed ?? 0
  const total = view.progress.total
  const share = total ? Math.round((100 * (done + failed)) / total) : 0
  return (
    <Card>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm text-ink-2">
          <span className="tabular text-2xl font-semibold text-ink">{done}</span> of <span className="tabular">{total}</span>{' '}
          postings checked{failed > 0 && `, ${failed} failed`}
        </p>
        <p className="text-sm text-muted">
          {view.finished ? 'Finished' : 'Running…'}
          {view.resumed && ' · resumed after a restart'}
        </p>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-grid" role="progressbar" aria-valuenow={share} aria-valuemin={0} aria-valuemax={100}>
        <div className="h-full rounded-full bg-accent transition-[width] duration-500" style={{ width: `${share}%` }} />
      </div>
      <div className="mt-4 flex flex-wrap gap-2" role="group" aria-label="Filter by verdict">
        {FILTERS.map((f) => {
          const count = f === 'all' ? done : (view.verdicts[f as Label] ?? 0)
          return (
            <button
              key={f}
              onClick={() => onFilter(f)}
              aria-pressed={filter === f}
              className={`rounded-full border px-3 py-1 text-sm ${filter === f ? 'border-ink bg-ink text-page' : 'border-line hover:bg-line'}`}
            >
              {f === 'all' ? 'All' : labelName(f)} <span className="tabular">{count}</span>
            </button>
          )
        })}
      </div>
      {Object.keys(view.fetch_errors).length > 0 && (
        <p className="mt-3 text-sm text-ink-2">Could not fetch: {Object.keys(view.fetch_errors).join(', ')}</p>
      )}
    </Card>
  )
}

function Row({ row }: { row: BatchRow }) {
  const signal = row.verdict?.deciding[0]
  return (
    <li className="grid grid-cols-1 gap-2 p-4 sm:grid-cols-[1fr_auto] sm:items-start sm:gap-4">
      <div className="min-w-0">
        <a href={safeHref(row.url)} target="_blank" rel="noreferrer" className="font-medium hover:underline">
          {row.title}
        </a>
        <p className="text-sm text-ink-2">
          {row.company} · {row.location}
        </p>
        {signal ? (
          <p className="mt-1 line-clamp-2 text-sm text-ink-2">
            <span className="text-muted">{SIGNAL_NAMES[signal.type] ?? signal.type}:</span> “{signal.quote}”
          </p>
        ) : (
          row.verdict && <p className="mt-1 text-sm text-muted">Says nothing about work authorization.</p>
        )}
      </div>
      <div className="sm:pt-0.5">
        {row.verdict ? (
          <VerdictBadge label={row.verdict.label} />
        ) : (
          <span className="text-xs text-muted">{row.state === 'failed' ? 'Failed' : 'In the queue…'}</span>
        )}
      </div>
    </li>
  )
}
