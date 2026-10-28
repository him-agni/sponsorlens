import { useEffect, useState } from 'react'
import { api, loadSample, type BatchRow, type BatchView, type Label, type SampleBatch, type Status } from './api'
import { LabelIcon, Spinner } from './components'
import { SIGNAL_NAMES } from './lib'

type Scan = { id: string; company: string; found: number; scanning: number }

const GROUPS: { label: Label; name: string; tint: string }[] = [
  { label: 'clear', name: 'Open to you', tint: 'bg-good/12' },
  { label: 'unclear', name: 'Ask first', tint: 'bg-warning/18' },
  { label: 'blocked', name: 'Not open to you', tint: 'bg-critical/12' },
]
const ORDER: Record<Label, number> = { clear: 0, unclear: 1, blocked: 2 }
// Boards with a recorded scan, so the examples work while the engine sleeps. For H-1B they range
// from all open (Anthropic sponsors) through a mix (Scale AI) to all closed (SpaceX, export control).
const EXAMPLES = [
  { token: 'scaleai', name: 'Scale AI' },
  { token: 'anthropic', name: 'Anthropic' },
  { token: 'spacex', name: 'SpaceX' },
  { token: 'robinhood', name: 'Robinhood' },
]
const PAGE = 6

export function BoardScan({ status, live }: { status: Status; live: boolean }) {
  const [url, setUrl] = useState('')
  const [keyword, setKeyword] = useState('')
  const [scan, setScan] = useState<Scan | null>(null)
  const [view, setView] = useState<BatchView | null>(null)
  const [example, setExample] = useState<string | null>(EXAMPLES[0].token)
  const [error, setError] = useState<string | null>(null)
  const [starting, setStarting] = useState(false)
  const [sample, setSample] = useState<SampleBatch | null>(null)

  useEffect(() => {
    loadSample<SampleBatch>('batch')
      .then(setSample)
      .catch(() => setSample(null))
  }, [])

  // Poll a live scan until it finishes; the status can change while it runs.
  useEffect(() => {
    if (!scan) return
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | undefined
    const poll = async () => {
      try {
        const next = await api<BatchView>(`/api/batch/${scan.id}?status=${status}`)
        if (cancelled) return
        setView(next)
        if (!next.finished) timer = setTimeout(poll, 1500)
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e))
      }
    }
    poll()
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [scan, status])

  async function start() {
    setStarting(true)
    setError(null)
    try {
      const started = await api<Scan>('/api/scan', {
        method: 'POST',
        body: JSON.stringify({ url: url.trim(), keyword: keyword.trim() || null, status }),
      })
      setExample(null)
      setView(null)
      setScan(started)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setStarting(false)
    }
  }

  function pickExample(token: string) {
    setError(null)
    if (live) {
      setUrl(`https://job-boards.greenhouse.io/${token}`)
      return
    }
    setScan(null)
    setExample(token)
  }

  // A live scan's rows, or one company's rows from the recorded 200-job run.
  const rows: BatchRow[] = scan
    ? (view?.items ?? [])
    : example && sample
      ? sample.views[status].items.filter((row) => row.source.startsWith(`greenhouse:${example}:`))
      : []
  const pending = scan ? (view?.progress.total ?? scan.scanning) - (view?.progress.done ?? 0) - (view?.progress.failed ?? 0) : 0
  const exampleName = EXAMPLES.find((e) => e.token === example)?.name

  return (
    <div className="grid gap-6">
      <div className="rounded-3xl border border-line bg-surface p-5 sm:p-6">
        <div className="grid gap-3 sm:grid-cols-[1fr_12rem_auto]">
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && live && url.trim() && start()}
            placeholder="https://job-boards.greenhouse.io/stripe"
            aria-label="Greenhouse job board link"
            className="w-full rounded-xl border border-line bg-page px-3.5 py-2.5 text-sm placeholder:text-muted focus:outline-2 focus:outline-accent"
          />
          <input
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="Title keyword (optional)"
            aria-label="Only titles containing"
            className="w-full rounded-xl border border-line bg-page px-3.5 py-2.5 text-sm placeholder:text-muted focus:outline-2 focus:outline-accent"
          />
          <button
            onClick={start}
            disabled={!live || starting || !url.trim() || (!!scan && !view?.finished)}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-brand px-5 py-2.5 text-sm font-semibold text-white transition hover:brightness-110 disabled:opacity-40"
          >
            {starting && <Spinner />}
            Scan board
          </button>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
          <span className="text-ink-2">{live ? 'Try:' : 'See a recorded scan:'}</span>
          {EXAMPLES.map((e) => (
            <button
              key={e.token}
              onClick={() => pickExample(e.token)}
              aria-pressed={!live && example === e.token}
              className={`rounded-full border px-3 py-1 transition ${
                !live && example === e.token ? 'border-brand bg-brand-soft text-ink' : 'border-line text-ink-2 hover:bg-line'
              }`}
            >
              {e.name}
            </button>
          ))}
        </div>
        <p className="mt-3 text-xs text-muted">
          Greenhouse boards for now. {live ? 'The public demo checks up to 10 jobs per scan.' : 'Scanning a new board needs the live engine.'}
        </p>
        {error && <p className="mt-3 text-sm text-critical-ink">{error}</p>}
      </div>

      {(scan || rows.length > 0) && (
        <Results
          rows={rows}
          title={scan ? `${scan.company} jobs` : `${exampleName} jobs`}
          note={
            scan
              ? scan.found > scan.scanning
                ? `Checked the first ${scan.scanning} of ${scan.found.toLocaleString()} US jobs${keyword ? ' matching' : ''}. Add a title keyword to narrow it.`
                : `All ${scan.found} US jobs${keyword ? ' matching' : ''} on the board.`
              : `Recorded live on ${shortDate(sample?.recorded)}, as part of a 200-job scan.`
          }
          pending={pending}
        />
      )}
    </div>
  )
}

function shortDate(iso?: string): string {
  if (!iso) return 'Oct 27'
  return new Date(`${iso}T12:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function Results({ rows, title, note, pending }: { rows: BatchRow[]; title: string; note: string; pending: number }) {
  const [filter, setFilter] = useState<Label | 'all'>('all')
  const [limit, setLimit] = useState(PAGE)
  const done = rows.filter((r) => r.verdict).sort((a, b) => ORDER[a.verdict!.label] - ORDER[b.verdict!.label])
  const shown = done.filter((r) => filter === 'all' || r.verdict!.label === filter)
  const count = (label: Label) => done.filter((r) => r.verdict!.label === label).length

  return (
    <section className="animate-rise">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="text-2xl font-semibold capitalize tracking-tight">{title}</h3>
        <span className="rounded-full border border-line px-3 py-0.5 text-sm tabular">{done.length}</span>
        {pending > 0 && (
          <span className="inline-flex items-center gap-2 text-sm text-ink-2">
            <Spinner /> Checking {pending} more…
          </span>
        )}
      </div>
      <p className="mt-1 text-sm text-muted">{note}</p>
      <div className="mt-4 flex flex-wrap gap-2" role="tablist" aria-label="Filter by verdict">
        {[{ label: 'all' as const, name: 'All' }, ...GROUPS].map((g) => {
          const n = g.label === 'all' ? done.length : count(g.label)
          return (
            <button
              key={g.label}
              role="tab"
              aria-selected={filter === g.label}
              onClick={() => {
                setFilter(g.label)
                setLimit(PAGE)
              }}
              className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm transition ${
                filter === g.label ? 'border-ink bg-ink text-page' : 'border-line text-ink-2 hover:bg-line'
              }`}
            >
              {g.label !== 'all' && <LabelIcon label={g.label} className="size-3.5" />}
              {g.name} <span className="tabular opacity-70">{n}</span>
            </button>
          )
        })}
      </div>
      <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {shown.slice(0, limit).map((row, i) => (
          <JobCard key={row.job_id} row={row} index={i} />
        ))}
        {pending > 0 &&
          filter === 'all' &&
          Array.from({ length: Math.min(pending, 3) }, (_, i) => (
            <div key={`pending-${i}`} className="h-56 animate-pulse rounded-3xl border border-line bg-brand-soft/70" />
          ))}
      </div>
      {shown.length > limit && (
        <div className="mt-5 text-center">
          <button onClick={() => setLimit(shown.length)} className="rounded-full border border-line bg-surface px-5 py-2 text-sm font-medium hover:bg-line">
            Show all {shown.length}
          </button>
        </div>
      )}
      {shown.length === 0 && pending === 0 && <p className="mt-4 text-sm text-ink-2">No jobs with this verdict.</p>}
    </section>
  )
}

function JobCard({ row, index }: { row: BatchRow; index: number }) {
  const [open, setOpen] = useState(false)
  const verdict = row.verdict!
  const group = GROUPS.find((g) => g.label === verdict.label)!
  const reasons = [...new Set(verdict.deciding.map((s) => SIGNAL_NAMES[s.type] ?? s.type))]
  const tags = reasons.length ? reasons : [verdict.label === 'clear' ? 'No restrictions found' : 'Says nothing about visas']
  const company = row.company_name ?? row.company

  return (
    <article
      className="flex animate-rise flex-col rounded-3xl border border-line bg-surface p-2 transition hover:-translate-y-0.5 hover:shadow-lg"
      style={{ animationDelay: `${Math.min(index, 8) * 60}ms` }}
    >
      <div className={`flex-1 rounded-2xl p-4 ${group.tint}`}>
        <div className="flex items-center justify-between gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-surface px-2.5 py-1 text-xs font-semibold">
            <LabelIcon label={verdict.label} className="size-3.5" />
            {group.name}
          </span>
        </div>
        <div className="mt-4 flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs text-ink-2">{company}</p>
            <h4 className="mt-0.5 line-clamp-2 text-lg leading-snug font-semibold">{row.title}</h4>
          </div>
          <span
            className="flex size-9 shrink-0 items-center justify-center rounded-full bg-ink text-sm font-bold text-page"
            aria-hidden="true"
          >
            {company.charAt(0).toUpperCase()}
          </span>
        </div>
        <div className="mt-4 flex flex-wrap gap-1.5">
          {tags.map((tag) => (
            <span key={tag} className="rounded-full border border-ink/25 px-2.5 py-0.5 text-xs">
              {tag}
            </span>
          ))}
        </div>
      </div>
      {open && (
        <div className="px-3 pt-3 text-sm">
          {verdict.deciding.slice(0, 2).map((s, i) => (
            <p key={i} className="mb-2 line-clamp-3 border-l-2 border-axis pl-2 text-ink-2">
              “{s.quote}”
            </p>
          ))}
          <p className="text-ink-2">{verdict.next_step}</p>
        </div>
      )}
      <div className="flex items-center justify-between gap-2 px-3 py-3">
        <p className="min-w-0 truncate text-xs text-muted">{row.location || 'Location not listed'}</p>
        <div className="flex shrink-0 gap-1.5">
          <button
            onClick={() => setOpen((o) => !o)}
            aria-expanded={open}
            className="rounded-full bg-ink px-3.5 py-1.5 text-xs font-semibold text-page"
          >
            {open ? 'Less' : 'Details'}
          </button>
          <a
            href={row.url}
            target="_blank"
            rel="noreferrer"
            aria-label={`Open the posting for ${row.title}`}
            className="rounded-full border border-line px-2.5 py-1.5 text-xs text-ink-2 hover:bg-line"
          >
            ↗
          </a>
        </div>
      </div>
    </article>
  )
}
