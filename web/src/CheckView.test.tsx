import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { SampleExamples } from './api'
import { CheckView } from './CheckView'
import { sample, serve } from './test/network'

const examples = sample<SampleExamples>('examples').examples
const noSponsorship = examples.find((e) => e.title.startsWith('No sponsorship'))!
const exportControl = examples.find((e) => e.title.startsWith('Export control'))!

function check(live: boolean, status: 'h1b' | 'ead' = 'h1b') {
  return render(<CheckView status={status} onStatus={() => {}} live={live} />)
}

describe('CheckView with the engine asleep', () => {
  it('shows a recorded example answer before anything is pasted', async () => {
    serve()
    check(false)
    expect(await screen.findByText(/Example answer for a sample posting/)).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Not open to people who need H-1B sponsorship' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Check posting' })).toHaveProperty('disabled', true)
  })

  it('answers for the status picked', async () => {
    serve()
    const view = check(false, 'h1b')
    await screen.findByText(/Example answer/)
    view.rerender(<CheckView status="ead" onStatus={() => {}} live={false} />)
    expect(screen.getByRole('heading', { name: 'Open to EAD holders' })).toBeTruthy()
  })

  it('opens another example, and Start over goes back to the first', async () => {
    serve()
    check(false)
    fireEvent.click(await screen.findByRole('button', { name: exportControl.title }))
    expect((screen.getByLabelText(/Paste a job description/) as HTMLTextAreaElement).value).toBe(exportControl.text)
    expect(screen.queryByText(/Example answer/)).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Start over' }))
    expect((screen.getByLabelText(/Paste a job description/) as HTMLTextAreaElement).value).toBe('')
    expect(screen.getByText(/Example answer/)).toBeTruthy()
  })
})

describe('CheckView with the engine live', () => {
  it('sends the posting and the status, then shows the verdict and the facts at a glance', async () => {
    const calls = serve({ '/api/analyze': noSponsorship.response })
    check(true)
    fireEvent.change(await screen.findByLabelText(/Paste a job description/), { target: { value: noSponsorship.text } })
    fireEvent.click(screen.getByRole('button', { name: 'Check posting' }))

    expect(await screen.findByRole('heading', { name: 'Not open to people who need H-1B sponsorship' })).toBeTruthy()
    const [, init] = calls.mock.calls.find(([url]) => String(url).endsWith('/api/analyze'))!
    expect(JSON.parse(String(init!.body))).toEqual({ text: noSponsorship.text, status: 'h1b' })
    if (noSponsorship.response.glance?.facts.length) expect(screen.getByText('At a glance')).toBeTruthy()
  })

  it('reads a link into the box first, then checks that text with the link’s employer', async () => {
    const calls = serve({
      '/api/read-link': { url: 'https://jobs.lever.co/acme/1', title: null, company: 'Acme', text: noSponsorship.text },
      '/api/analyze': noSponsorship.response,
    })
    check(true)
    fireEvent.change(await screen.findByLabelText(/Paste a job description/), { target: { value: 'https://jobs.lever.co/acme/1' } })
    fireEvent.click(screen.getByRole('button', { name: 'Check link' }))

    expect(await screen.findByText('jobs.lever.co')).toBeTruthy()
    await screen.findByRole('heading', { name: 'Not open to people who need H-1B sponsorship' })
    const analyzed = calls.mock.calls.find(([url]) => String(url).endsWith('/api/analyze'))!
    expect(JSON.parse(String(analyzed[1]!.body))).toMatchObject({ text: noSponsorship.text, company: 'Acme' })
  })

  it('shows what the API says when it refuses', async () => {
    serve({ '/api/analyze': Response.json({ detail: 'The live demo is busy this hour.' }, { status: 429 }) })
    check(true)
    fireEvent.change(await screen.findByLabelText(/Paste a job description/), { target: { value: 'Some posting' } })
    fireEvent.click(screen.getByRole('button', { name: 'Check posting' }))
    await waitFor(() => expect(screen.getByText('The live demo is busy this hour.')).toBeTruthy())
  })
})
