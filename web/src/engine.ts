import { useEffect, useState } from 'react'
import { API_URL } from './api'

// 'ended': the hosted demo is past its last live day and makes no paid calls; the app shows recordings.
export type EngineState = 'checking' | 'waking' | 'live' | 'no-engine' | 'ended' | 'offline'

export type Engine = {
  state: EngineState
  /** False on the hosted demo, where batches would spend credits; the app shows the recorded batch instead. */
  liveBatches: boolean
}

/** Whether the live engine can answer. Anything but 'live' means the app shows its sample run. */
export function useEngine(): Engine {
  const [state, setState] = useState<EngineState>('checking')
  const [liveBatches, setLiveBatches] = useState(false)

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
        const { live, live_batches } = await health.json()
        if (!cancelled) setLiveBatches(live_batches !== false)
        if (live === false) result = 'ended'
        else result = (await fetch(`${API_URL}/metrics`)).ok ? 'live' : 'no-engine'
      } catch {
        result = 'offline'
      } finally {
        clearTimeout(slow)
      }
      if (cancelled) return
      setState(result)
      // An ended demo stays ended; anything else not live may come back, so look again.
      if (result !== 'live' && result !== 'ended') retry = setTimeout(probe, 30_000)
    }

    probe()
    return () => {
      cancelled = true
      clearTimeout(retry)
    }
  }, [])

  return { state, liveBatches }
}
