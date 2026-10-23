import { useState } from 'react'

type PingResult = {
  model: string
  reply: string
  latency_ms: number
}

function App() {
  const [result, setResult] = useState<PingResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function ping() {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch('/api/ping-model')
      const body = await response.json()
      if (!response.ok) throw new Error(body.detail ?? response.statusText)
      setResult(body)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="mx-auto max-w-2xl px-4 py-16">
      <h1 className="text-3xl font-semibold">SponsorLens</h1>
      <p className="mt-2 text-gray-600">Phase 0: check the Nemotron connection.</p>
      <button
        onClick={ping}
        disabled={loading}
        className="mt-6 rounded-lg bg-gray-900 px-4 py-2 text-white disabled:opacity-50"
      >
        {loading ? 'Calling Nemotron…' : 'Ping the model'}
      </button>
      {error && <p className="mt-4 text-red-700">{error}</p>}
      {result && (
        <div className="mt-4 rounded-lg border border-gray-200 p-4">
          <p className="font-medium">{result.reply}</p>
          <p className="mt-1 text-sm text-gray-500">
            {result.model} · {result.latency_ms} ms
          </p>
        </div>
      )}
    </main>
  )
}

export default App
