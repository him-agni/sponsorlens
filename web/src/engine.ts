import { useEffect, useState } from 'react'
import { API_URL } from './api'

export type EngineState = 'checking' | 'waking' | 'live' | 'no-engine' | 'offline'

/** Whether the live engine can answer. Anything but 'live' means the app shows its sample run. */
export function useEngine(): EngineState {
  const [state, setState] = useState<EngineState>('checking')

  useEffect(() => {
    let cancelled = false
    let retry: ReturnType<typeof setTimeout> | undefined

    async function probe() {
      // The free host sleeps when idle; a health check that takes this long means it is waking.
      const slow = setTimeout(() => !cancelled && setState((s) => (s === 'live' ? s : 'waking')), 1500)
      let result: EngineState
      try {
        const health = await fetch(`${API_URL}/health`, { signal: AbortSignal.timeout(90_000) })
        if (!health.ok) throw new Error()
        const metrics = await fetch(`${API_URL}/metrics`)
        result = metrics.ok ? 'live' : 'no-engine'
      } catch {
        result = 'offline'
      } finally {
        clearTimeout(slow)
      }
      if (cancelled) return
      setState(result)
      if (result !== 'live') retry = setTimeout(probe, 30_000)
    }

    probe()
    return () => {
      cancelled = true
      clearTimeout(retry)
    }
  }, [])

  return state
}
