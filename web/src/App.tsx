import { Suspense, lazy, useEffect, useState } from 'react'
import { loadSample, type SampleExamples, type Status } from './api'
import { BatchView } from './BatchView'
import { Card, EngineBanner, StatusPicker, ThemeToggle } from './components'
import { useEngine } from './engine'
import { Home } from './Home'
import { useUrlParam } from './lib'

// The charts library is most of the bundle, so the dashboard loads only when its view opens.
const DashboardView = lazy(() => import('./DashboardView'))

// 'batch' and 'engine' are the two "Under the hood" views; the app itself is 'check'.
const VIEWS = ['check', 'batch', 'engine'] as const
const STATUS_IDS = ['ead', 'opt', 'h1b', 'green_card'] as const
const LINKS = [
  { href: '#check', name: 'Check a job' },
  { href: '#scan', name: 'Scan a board' },
  { href: '#how', name: 'How it works' },
  { href: '#faq', name: 'FAQ' },
]

function App() {
  const [view, setView] = useUrlParam<(typeof VIEWS)[number]>('view', 'check', VIEWS)
  const [status, setStatus] = useUrlParam<Status>('status', 'h1b', STATUS_IDS)
  const engine = useEngine()
  const live = engine.state === 'live'
  // Where batches are off, the batch and engine views replay the recorded run.
  const liveBatches = live && engine.liveBatches
  const [sample, setSample] = useState<{ recorded: string; backend: string }>()

  useEffect(() => {
    loadSample<SampleExamples>('examples')
      .then(({ recorded, backend }) => setSample({ recorded, backend }))
      .catch(() => {})
  }, [])

  return (
    <div className="flex min-h-screen flex-col">
      <EngineBanner state={engine.state} recorded={sample?.recorded} backend={sample?.backend} />
      <header className="sticky top-0 z-30 border-b border-line bg-page/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3">
          <button
            onClick={() => {
              setView('check')
              window.scrollTo({ top: 0, behavior: 'smooth' })
            }}
            aria-label="SponsorLens, back to the top"
            className="flex items-center gap-2 text-lg font-bold tracking-tight"
          >
            <span className="flex size-8 items-center justify-center rounded-xl bg-brand text-white">
              <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true">
                <circle cx="10.5" cy="10.5" r="6" />
                <path d="M15 15l5 5M8 10.5l1.8 1.8 3.2-3.6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
            SponsorLens
          </button>
          <nav className="hidden items-center gap-1 md:flex" aria-label="Sections">
            {view === 'check' &&
              LINKS.map((link) => (
                <a key={link.href} href={link.href} className="rounded-lg px-3 py-1.5 text-sm text-ink-2 transition hover:bg-line hover:text-ink">
                  {link.name}
                </a>
              ))}
          </nav>
          <div className="flex items-center gap-2">
            {view === 'check' ? (
              <button onClick={() => setView('engine')} className="rounded-lg px-2.5 py-1.5 text-sm font-medium whitespace-nowrap text-accent hover:bg-line">
                <span className="sm:hidden">Engine</span>
                <span className="hidden sm:inline">Under the hood</span>
              </button>
            ) : (
              <button onClick={() => setView('check')} className="rounded-lg px-2.5 py-1.5 text-sm font-medium text-accent hover:bg-line">
                ← Back
              </button>
            )}
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="flex-1">
        {view === 'check' ? (
          <Home status={status} onStatus={setStatus} live={live} />
        ) : (
          <div className="mx-auto w-full max-w-5xl px-4 pb-16">
            <section className="pt-10 pb-6">
              <span className="inline-block rounded-full border border-line px-4 py-1 text-sm">Under the hood</span>
              <h1 className="mt-4 text-3xl font-bold tracking-tight">
                The engine behind <span className="mark">every check</span>
              </h1>
              <p className="mt-2 max-w-2xl text-ink-2">
                Sharded queues with backpressure, a cache that never pays twice for the same posting, and a log that survives a
                crash. Live when the engine is busy; otherwise a replay of a real 200-job run.
              </p>
              <nav className="mt-6 flex gap-1 border-b border-line" aria-label="Under the hood">
                {(['engine', 'batch'] as const).map((v) => (
                  <button
                    key={v}
                    onClick={() => setView(v)}
                    aria-current={view === v ? 'page' : undefined}
                    className={`-mb-px border-b-2 px-3 py-2 text-sm ${
                      view === v ? 'border-brand font-semibold text-ink' : 'border-transparent text-ink-2 hover:text-ink'
                    }`}
                  >
                    {v === 'engine' ? 'Engine dashboard' : 'The 200-job run'}
                  </button>
                ))}
              </nav>
            </section>
            {view === 'batch' && (
              <>
                <div className="mb-6">
                  <p className="mb-1.5 text-sm font-medium">Show verdicts for</p>
                  <StatusPicker value={status} onChange={setStatus} />
                </div>
                <BatchView status={status} live={liveBatches} engineLive={live} />
              </>
            )}
            {view === 'engine' && (
              <Suspense fallback={<Card>Loading the dashboard…</Card>}>
                <DashboardView key={String(liveBatches)} live={liveBatches} />
              </Suspense>
            )}
          </div>
        )}
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-8 text-sm text-muted">
          <p>Information, not legal advice. Confirm with the employer or an immigration attorney.</p>
          <p>
            Built with NVIDIA Nemotron on Nebius Token Factory and Tavily ·{' '}
            <a href="https://github.com/him-agni/sponsorlens" className="underline hover:text-ink">
              GitHub
            </a>
          </p>
        </div>
      </footer>
    </div>
  )
}

export default App
