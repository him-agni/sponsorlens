// Empty in development, where Vite proxies to the local API; the API's URL on Render.
export const API_URL = import.meta.env.VITE_API_URL ?? ''

export type Status = 'ead' | 'opt' | 'h1b' | 'green_card'
export type Label = 'clear' | 'unclear' | 'blocked'

export type Signal = { type: string; quote: string; reading: string }

export type Analysis = {
  company: string | null
  signals: Signal[]
  unverified_quotes: number
  nano_model: string
  ultra_model: string
  prompt_version: string
}

export type Verdict = { status: Status; label: Label; deciding: Signal[]; notes: string[]; next_step: string }

export type CompanyContext = {
  company: string
  query: string
  sources: { title: string; url: string; snippet: string }[]
}

export type LinkedPosting = { url: string; title: string | null; company: string | null; text: string }

export type AnalyzeResponse = {
  analysis: Analysis
  verdict: Verdict
  verdicts: Record<Status, Verdict>
  text: string
  company_context: CompanyContext | null
}

export type BatchRow = {
  job_id: string
  source: string
  company: string
  title: string
  url: string
  location: string
  shard: number | null
  state: string
  error: string | null
  verdict: Verdict | null
  labels: Record<Status, Label> | null
}

export type BatchView = {
  id: string
  status: Status
  companies: string[]
  per_company: number
  finished: boolean
  resumed: boolean
  fetched: string[]
  fetch_errors: Record<string, string>
  progress: { total: number } & Record<string, number>
  verdicts: Partial<Record<Label, number>>
  items: BatchRow[]
}

export type Histogram = { count: number; p50: number | null; p95: number | null; max: number | null }

export type Snapshot = {
  backend: string
  uptime_s: number
  counters: Record<string, number>
  gauges: Record<string, number>
  histograms: Record<string, Histogram>
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: init?.body ? { 'Content-Type': 'application/json', ...init.headers } : init?.headers,
  })
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = body?.detail
    throw new Error(typeof detail === 'string' ? detail : `The engine answered ${response.status}`)
  }
  return body as T
}

// Sample mode: a recorded run, shipped with the web app, shown while the engine wakes or is off.
export type SampleExamples = {
  backend: string
  recorded: string
  examples: { id: string; title: string; text: string; response: AnalyzeResponse }[]
}
export type SampleBatch = { backend: string; recorded: string; views: Record<Status, BatchView> }
export type SampleMetrics = { backend: string; recorded: string; snapshots: Snapshot[] }

const samples = new Map<string, Promise<unknown>>()

export function loadSample<T>(name: 'examples' | 'batch' | 'metrics'): Promise<T> {
  if (!samples.has(name)) {
    samples.set(
      name,
      fetch(`/sample/${name}.json`).then((r) => {
        if (!r.ok) throw new Error('No sample run is available')
        return r.json()
      }),
    )
  }
  return samples.get(name) as Promise<T>
}
