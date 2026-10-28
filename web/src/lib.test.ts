import { describe, expect, it } from 'vitest'
import type { Signal } from './api'
import { LABEL_STYLE, STATUSES, headline, highlight, safeHref } from './lib'

describe('headline', () => {
  it('names the reader for each verdict', () => {
    expect(headline('clear', 'ead')).toBe('Open to EAD holders')
    expect(headline('blocked', 'h1b')).toBe('Not open to people who need H-1B sponsorship')
    expect(headline('unclear', 'opt')).toBe("The posting doesn't settle it for OPT and STEM OPT")
  })
})

describe('safeHref', () => {
  it('keeps http and https links', () => {
    expect(safeHref('https://job-boards.greenhouse.io/stripe/jobs/1')).toBe('https://job-boards.greenhouse.io/stripe/jobs/1')
    expect(safeHref('http://example.com/a')).toBe('http://example.com/a')
  })

  it('drops anything that could run script, and junk', () => {
    expect(safeHref('javascript:alert(1)')).toBeUndefined()
    expect(safeHref('data:text/html,<script>alert(1)</script>')).toBeUndefined()
    expect(safeHref('not a url')).toBeUndefined()
    expect(safeHref(null)).toBeUndefined()
  })
})

describe('highlight', () => {
  const text = 'We build rockets.\nApplicants must be U.S. citizens.\nWe do not sponsor visas.'
  const citizens: Signal = { type: 'us_citizens_only', quote: 'Applicants must be U.S. citizens', reading: 'r' }
  const sponsor: Signal = { type: 'no_sponsorship', quote: 'we do NOT sponsor   visas.', reading: 'r' }

  it('marks each quote, ignoring case and spacing, and keeps the rest as plain text', () => {
    const segments = highlight(text, [citizens, sponsor], [sponsor])
    expect(segments.map((s) => s.text).join('')).toBe(text)
    const marked = segments.filter((s) => s.signal)
    expect(marked.map((s) => s.text)).toEqual(['Applicants must be U.S. citizens', 'We do not sponsor visas'])
    expect(marked.map((s) => s.deciding)).toEqual([false, true])
  })

  it('leaves a quote that is not in the text unmarked', () => {
    const invented: Signal = { type: 'e_verify', quote: 'We use E-Verify', reading: 'r' }
    expect(highlight(text, [invented], [])).toEqual([{ text }])
  })
})

describe('label styles', () => {
  it('give every verdict a name, fill, tint and highlight', () => {
    for (const style of Object.values(LABEL_STYLE)) {
      expect(style.name && style.fill && style.tint && style.mark).toBeTruthy()
    }
    expect(STATUSES.map((s) => s.id)).toEqual(['ead', 'opt', 'h1b', 'green_card'])
  })
})
