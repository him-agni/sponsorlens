import { useEffect, useMemo, useState } from 'react'
import { api, loadSample, type AnalyzeResponse, type CompanyContext, type SampleExamples, type Status } from './api'
import { Card, LabelIcon, Spinner, VerdictBadge } from './components'
import { SIGNAL_NAMES, STATUSES, headline, highlight, labelInk, labelName } from './lib'

type Props = { status: Status; onStatus: (s: Status) => void; live: boolean }

export function CheckView({ status, onStatus, live }: Props) {
  const [text, setText] = useState('')
  const [result, setResult] = useState<AnalyzeResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [examples, setExamples] = useState<SampleExamples['examples']>([])
  const [contexts, setContexts] = useState<Record<string, CompanyContext | null>>({})

  useEffect(() => {
    loadSample<SampleExamples>('examples')
      .then((s) => setExamples(s.examples))
      .catch(() => setExamples([]))
  }, [])

  const verdict = result?.verdicts[status]
  const company = result?.analysis.company ?? null

  // A status switched to Unclear may need company context the first answer didn't include.
  const needsContext =
    live && verdict?.label === 'unclear' && !!company && !result?.company_context && !(company in contexts)
  useEffect(() => {
    if (!needsContext || !company) return
    api<CompanyContext | null>(`/api/company-context?company=${encodeURIComponent(company)}`)
      .then((context) => setContexts((c) => ({ ...c, [company]: context })))
      .catch(() => setContexts((c) => ({ ...c, [company]: null })))
  }, [needsContext, company])

  async function check(posting: string) {
    setLoading(true)
    setError(null)
    try {
      setResult(await api<AnalyzeResponse>('/api/analyze', { method: 'POST', body: JSON.stringify({ text: posting, status }) }))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  function tryExample(example: SampleExamples['examples'][number]) {
    setText(example.text)
    setError(null)
    if (live) check(example.text)
    else setResult(example.response)
  }

  const context = result?.company_context ?? (company ? (contexts[company] ?? null) : null)

  return (
    <div className="grid gap-6">
      <Card>
        <label htmlFor="posting" className="text-sm font-medium">
          Paste a job posting
        </label>
        <textarea
          id="posting"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={7}
          placeholder="Paste the full posting, including the benefits and legal sections at the bottom."
          className="mt-2 w-full resize-y rounded-xl border border-line bg-page p-3 text-sm leading-relaxed placeholder:text-muted focus:outline-2 focus:outline-accent"
        />
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <button
            onClick={() => check(text)}
            disabled={!live || loading || !text.trim()}
            className="inline-flex items-center gap-2 rounded-lg bg-ink px-4 py-2 text-sm font-medium text-page disabled:opacity-40"
          >
            {loading && <Spinner />}
            {loading ? 'Reading the posting…' : 'Check posting'}
          </button>
          {!live && <span className="text-sm text-muted">Checking new text needs the live engine. The examples work now.</span>}
        </div>
        {examples.length > 0 && (
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span className="text-sm text-ink-2">Try an example:</span>
            {examples.map((ex) => (
              <button
                key={ex.id}
                onClick={() => tryExample(ex)}
                className="rounded-full border border-line px-3 py-1 text-sm text-ink-2 hover:bg-line"
              >
                {ex.title}
              </button>
            ))}
          </div>
        )}
        {error && <p className="mt-3 text-sm text-critical-ink">{error}</p>}
      </Card>

      {result && verdict && (
        <>
          <VerdictCard result={result} status={status} onStatus={onStatus} />
          {verdict.label === 'unclear' && <ContextPanel company={company} context={context} />}
          <PostingText result={result} status={status} />
        </>
      )}
    </div>
  )
}

function VerdictCard({ result, status, onStatus }: { result: AnalyzeResponse; status: Status; onStatus: (s: Status) => void }) {
  const verdict = result.verdicts[status]
  return (
    <Card>
      <div className="flex flex-wrap items-center gap-3">
        <VerdictBadge label={verdict.label} size="lg" />
        {result.analysis.company && <span className="text-sm text-ink-2">{result.analysis.company}</span>}
      </div>
      <h2 className="mt-3 text-2xl font-semibold tracking-tight">{headline(verdict.label, status)}</h2>

      {verdict.deciding.length > 0 ? (
        <ul className="mt-4 grid gap-3">
          {verdict.deciding.map((signal, i) => (
            <li key={i} className="border-l-2 border-axis pl-3">
              <p className="text-xs font-medium uppercase tracking-wide text-muted">{SIGNAL_NAMES[signal.type] ?? signal.type}</p>
              <blockquote className="mt-0.5 text-ink">“{signal.quote}”</blockquote>
              {signal.reading && <p className="mt-1 text-sm text-ink-2">{signal.reading}</p>}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-ink-2">The posting says nothing about sponsorship, citizenship, clearances or work authorization.</p>
      )}

      {verdict.notes.map((note, i) => (
        <p key={i} className="mt-3 text-sm text-ink-2">
          {note}
        </p>
      ))}

      <div className="mt-4 rounded-xl bg-page p-3">
        <p className="text-xs font-medium uppercase tracking-wide text-muted">Next step</p>
        <p className="mt-1 text-sm">{verdict.next_step}</p>
      </div>

      <div className="mt-5 border-t border-line pt-4">
        <p className="text-sm text-ink-2">The same posting, for each status:</p>
        <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {STATUSES.map((s) => {
            const label = result.verdicts[s.id].label
            return (
              <button
                key={s.id}
                onClick={() => onStatus(s.id)}
                aria-pressed={s.id === status}
                className={`flex flex-col items-start gap-0.5 rounded-lg border px-3 py-2 text-left text-sm lg:flex-row lg:items-center lg:justify-between lg:gap-2 ${
                  s.id === status ? 'border-ink' : 'border-line hover:bg-line'
                }`}
              >
                <span>{s.short}</span>
                <span className={`inline-flex items-center gap-1 font-medium ${labelInk(label)}`}>
                  <LabelIcon label={label} className="size-3.5" />
                  {labelName(label)}
                </span>
              </button>
            )
          })}
        </div>
      </div>
    </Card>
  )
}

function ContextPanel({ company, context }: { company: string | null; context: CompanyContext | null }) {
  return (
    <Card>
      <p className="text-xs font-medium uppercase tracking-wide text-muted">Company context · from the web, not the posting</p>
      <h3 className="mt-1 font-semibold">Has {company ?? 'this company'} sponsored visas before?</h3>
      {context && context.sources.length > 0 ? (
        <ul className="mt-3 grid gap-3">
          {context.sources.map((source) => (
            <li key={source.url}>
              <a href={source.url} target="_blank" rel="noreferrer" className="font-medium text-accent hover:underline">
                {source.title}
              </a>
              <p className="mt-0.5 line-clamp-2 text-sm text-ink-2">{source.snippet}</p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-sm text-ink-2">
          {context
            ? `The web search found nothing about ${company ?? 'this company'} itself, only general lists. Ask the recruiter directly.`
            : 'Web context is not available right now. Ask the recruiter directly.'}
        </p>
      )}
      <p className="mt-3 text-xs text-muted">Search results via Tavily. They give background only and never change the verdict.</p>
    </Card>
  )
}

function PostingText({ result, status }: { result: AnalyzeResponse; status: Status }) {
  const verdict = result.verdicts[status]
  const segments = useMemo(
    () => highlight(result.text, result.analysis.signals, verdict.deciding),
    [result, verdict],
  )
  const tint = { clear: 'bg-good/20', unclear: 'bg-warning/30', blocked: 'bg-critical/20' }[verdict.label]
  return (
    <Card>
      <p className="text-xs font-medium uppercase tracking-wide text-muted">The posting, with the lines that decide it marked</p>
      <div className="mt-3 max-h-[28rem] overflow-y-auto whitespace-pre-wrap text-sm leading-relaxed text-ink-2">
        {segments.map((segment, i) =>
          segment.signal ? (
            <mark
              key={i}
              title={segment.signal.reading}
              className={`rounded px-0.5 text-ink ${segment.deciding ? `${tint} underline decoration-2 underline-offset-2` : 'bg-line'}`}
            >
              {segment.text}
            </mark>
          ) : (
            <span key={i}>{segment.text}</span>
          ),
        )}
      </div>
    </Card>
  )
}
