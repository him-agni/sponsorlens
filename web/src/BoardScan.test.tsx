import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { SampleBatch } from './api'
import { BoardScan } from './BoardScan'
import { sample, serve } from './test/network'

const recorded = sample<SampleBatch>('batch').views.h1b
const spacex = { ...recorded, finished: true, items: recorded.items.filter((r) => r.source.startsWith('greenhouse:spacex:')) }

function cards() {
  return screen.queryAllByRole('article')
}

describe('BoardScan with the engine asleep', () => {
  it('shows a recorded scan, sorted and filterable by verdict', async () => {
    serve()
    render(<BoardScan status="h1b" live={false} />)
    expect(await screen.findByRole('heading', { name: 'Scale AI jobs' })).toBeTruthy()
    const shown = cards().length
    expect(shown).toBeGreaterThan(0)

    fireEvent.click(screen.getByRole('tab', { name: /Not open to you/ }))
    expect(cards().every((card) => within(card).queryByText('Not open to you'))).toBe(true)
    expect(screen.getByRole('button', { name: 'Scan board' })).toHaveProperty('disabled', true)
  })

  it('switches between recorded companies', async () => {
    serve()
    render(<BoardScan status="h1b" live={false} />)
    fireEvent.click(await screen.findByRole('button', { name: 'SpaceX' }))
    expect(await screen.findByRole('heading', { name: 'SpaceX jobs' })).toBeTruthy()
  })
})

describe('BoardScan with the engine live', () => {
  it('starts a scan and shows each job as a card with its reasons', async () => {
    const calls = serve({
      '/api/scan': { id: 'abc123', company: 'spacex', found: 1432, scanning: spacex.items.length },
      '/api/batch/abc123': spacex,
    })
    render(<BoardScan status="h1b" live />)
    fireEvent.change(screen.getByLabelText(/careers page or job board link/), {
      target: { value: 'https://www.spacex.com/careers' },
    })
    fireEvent.change(screen.getByLabelText('Only titles containing'), { target: { value: 'engineer' } })
    fireEvent.click(screen.getByRole('button', { name: 'Scan board' }))

    expect(await screen.findByText(/Checked the first \d+ of 1,432 US jobs matching/)).toBeTruthy()
    // The cards come with the first poll, a moment after the scan starts.
    expect(await screen.findAllByRole('article')).toHaveLength(Math.min(6, spacex.items.filter((r) => r.verdict).length))
    const [, init] = calls.mock.calls.find(([url]) => String(url).endsWith('/api/scan'))!
    expect(JSON.parse(String(init!.body))).toEqual({ url: 'https://www.spacex.com/careers', keyword: 'engineer', status: 'h1b' })

    fireEvent.click(within(cards()[0]).getByRole('button', { name: 'Details' }))
    expect(within(cards()[0]).getByRole('button', { name: 'Less' })).toBeTruthy()
  })

  it('Start over clears the link, the keyword and the results', async () => {
    serve({
      '/api/scan': { id: 'abc123', company: 'spacex', found: 3, scanning: 3 },
      '/api/batch/abc123': spacex,
    })
    render(<BoardScan status="h1b" live />)
    const link = screen.getByLabelText(/careers page or job board link/) as HTMLInputElement
    const keyword = screen.getByLabelText('Only titles containing') as HTMLInputElement
    fireEvent.change(link, { target: { value: 'https://www.spacex.com/careers' } })
    fireEvent.change(keyword, { target: { value: 'engineer' } })
    fireEvent.click(screen.getByRole('button', { name: 'Scan board' }))
    await screen.findByRole('heading', { name: 'spacex jobs' })

    fireEvent.click(screen.getByRole('button', { name: 'Start over' }))
    expect([link.value, keyword.value]).toEqual(['', ''])
    expect(screen.queryByRole('heading', { name: 'spacex jobs' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Start over' })).toBeNull()
  })

  it('explains a link it cannot scan', async () => {
    serve({ '/api/scan': Response.json({ detail: "Couldn't find a Greenhouse job board for www.notion.so." }, { status: 422 }) })
    render(<BoardScan status="h1b" live />)
    fireEvent.change(screen.getByLabelText(/careers page or job board link/), { target: { value: 'https://www.notion.so/careers' } })
    fireEvent.click(screen.getByRole('button', { name: 'Scan board' }))
    expect(await screen.findByText(/Couldn't find a Greenhouse job board for www.notion.so/)).toBeTruthy()
  })
})
