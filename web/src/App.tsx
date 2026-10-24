import { useState } from 'react'

// Empty in development, where Vite proxies to the local API; the API's URL on Render.
const API_URL = import.meta.env.VITE_API_URL ?? ''

type HealthResult = {
  status: string
  latency_ms: number
}

function App() {
  const [result, setResult] = useState<HealthResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function check() {
    setLoading(true)
    setError(null)
    const start = performance.now()
    try {
      const response = await fetch(`${API_URL}/health`)
      const body = await response.json()
      if (!response.ok) throw new Error(body.detail ?? response.statusText)
      setResult({ ...body, latency_ms: Math.round(performance.now() - start) })
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="mx-auto max-w-2xl px-4 py-16">
      <h1 className="text-3xl font-semibold">SponsorLens</h1>
      <p className="mt-2 text-gray-600">Check whether the engine is awake. On the free tier it sleeps when idle and takes about a minute to wake.</p>
      <button
        onClick={check}
        disabled={loading}
        className="mt-6 rounded-lg bg-gray-900 px-4 py-2 text-white disabled:opacity-50"
      >
        {loading ? 'Waking the engine…' : 'Check the engine'}
      </button>
      {error && <p className="mt-4 text-red-700">{error}</p>}
      {result && (
        <div className="mt-4 rounded-lg border border-gray-200 p-4">
          <p className="font-medium">Engine status: {result.status}</p>
          <p className="mt-1 text-sm text-gray-500">Answered in {result.latency_ms} ms</p>
        </div>
      )}
    </main>
  )
}

export default App
