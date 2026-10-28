import { renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { useEngine } from './engine'
import { serve } from './test/network'

describe('useEngine', () => {
  it('is live when health and metrics answer', async () => {
    serve({ '/health': { status: 'ok', live: true, live_batches: false }, '/metrics': { counters: {} } })
    const { result } = renderHook(() => useEngine())
    await waitFor(() => expect(result.current.state).toBe('live'))
    expect(result.current.liveBatches).toBe(false)
  })

  it('is ended after the last live day, without asking for metrics', async () => {
    const calls = serve({ '/health': { status: 'ok', live: false, live_batches: false } })
    const { result } = renderHook(() => useEngine())
    await waitFor(() => expect(result.current.state).toBe('ended'))
    expect(calls.mock.calls.map(([url]) => String(url))).toEqual(['/health'])
  })

  it('has no engine when the API runs without a key', async () => {
    serve({ '/health': { status: 'ok', live: true }, '/metrics': new Response('{}', { status: 503 }) })
    const { result } = renderHook(() => useEngine())
    await waitFor(() => expect(result.current.state).toBe('no-engine'))
  })

  it('is offline when the API cannot be reached', async () => {
    serve({})
    const { result } = renderHook(() => useEngine())
    await waitFor(() => expect(result.current.state).toBe('offline'))
  })
})
