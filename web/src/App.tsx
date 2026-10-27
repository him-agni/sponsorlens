import { Suspense, lazy, useEffect, useState } from 'react'
import { loadSample, type SampleExamples, type Status } from './api'
import { BatchView } from './BatchView'
import { CheckView } from './CheckView'
import { Card, EngineBanner, StatusPicker } from './components'
import { useEngine } from './engine'
import { useUrlParam } from './lib'

// The charts library is most of the bundle, so the dashboard loads only when its tab opens.
const DashboardView = lazy(() => import('./DashboardView'))

const VIEWS = ['check', 'batch', 'engine'] as const
const STATUS_IDS = ['ead', 'opt', 'h1b', 'green_card'] as const
const TAB_NAMES = { check: 'Check a posting', batch: 'Batch', engine: 'Engine' }

function App() {
  const [view, setView] = useUrlParam<(typeof VIEWS)[number]>('view', 'check', VIEWS)
  const [status, setStatus] = useUrlParam<Status>('status', 'h1b', STATUS_IDS)
  const engine = useEngine()
  const live = engine === 'live'
  const [sample, setSample] = useState<{ recorded: string; backend: string }>()

  useEffect(() => {
    loadSample<SampleExamples>('examples')
      .then(({ recorded, backend }) => setSample({ recorded, backend }))
      .catch(() => {})
  }, [])

  return (
    <div className="flex min-h-screen flex-col">
      <EngineBanner state={engine} recorded={sample?.recorded} backend={sample?.backend} />
      <header className="border-b border-line">
        <div className="mx-auto max-w-5xl px-4 pt-6">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h1 className="text-2xl font-semibold tracking-tight">SponsorLens</h1>
            <span className="inline-flex items-center gap-1.5 text-xs text-ink-2">
              <span className={`size-2 rounded-full ${live ? 'bg-good' : 'bg-warning'}`} aria-hidden="true" />
              {live ? 'Engine live' : 'Sample mode'}
            </span>
          </div>
          <p className="mt-1 max-w-2xl text-ink-2">
            Is this job open to someone with your work authorization? SponsorLens reads the posting and answers with the exact
            lines that decide it.
          </p>
          <div className="mt-4">
            <p className="mb-1.5 text-sm font-medium">Your status</p>
            <StatusPicker value={status} onChange={setStatus} />
          </div>
          <nav className="mt-5 flex gap-1" aria-label="Views">
            {VIEWS.map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                aria-current={view === v ? 'page' : undefined}
                className={`-mb-px border-b-2 px-3 py-2 text-sm ${
                  view === v ? 'border-ink font-medium text-ink' : 'border-transparent text-ink-2 hover:text-ink'
                }`}
              >
                {TAB_NAMES[v]}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">
        {view === 'check' && <CheckView status={status} onStatus={setStatus} live={live} />}
        {view === 'batch' && <BatchView status={status} live={live} />}
        {view === 'engine' && (
          <Suspense fallback={<Card>Loading the dashboard…</Card>}>
            <DashboardView key={String(live)} live={live} />
          </Suspense>
        )}
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto max-w-5xl px-4 py-6 text-sm text-ink-2">
          <p>
            Information, not legal advice. A verdict reflects only what the posting says; confirm with the employer or an
            immigration attorney before you rely on it.
          </p>
          <p className="mt-2 text-muted">
            Built with NVIDIA Nemotron on Nebius Token Factory, with web context from Tavily ·{' '}
            <a href="https://github.com/him-agni/sponsorlens" className="underline hover:text-ink">
              Source on GitHub
            </a>
          </p>
        </div>
      </footer>
    </div>
  )
}

export default App
