import { useCallback, useEffect, useState } from 'react'
import type { Label, Signal, Status } from './api'

export const STATUSES: { id: Status; short: string; reader: string }[] = [
  { id: 'ead', short: 'EAD', reader: 'EAD holders' },
  { id: 'opt', short: 'OPT / STEM OPT', reader: 'OPT and STEM OPT' },
  { id: 'h1b', short: 'Needs H-1B', reader: 'people who need H-1B sponsorship' },
  { id: 'green_card', short: 'Green card', reader: 'green card holders' },
]

const statusInfo = (id: Status) => STATUSES.find((s) => s.id === id) ?? STATUSES[2]

// Status colors are fixed, and always shown with an icon and the label's name. `tint` is a soft
// card background; `mark` highlights a deciding line in the posting.
export const LABEL_STYLE: Record<Label, { name: string; fill: string; ink: string; onFill: string; tint: string; mark: string }> = {
  clear: { name: 'Clear', fill: 'bg-good', ink: 'text-good-ink', onFill: 'text-white', tint: 'bg-good/12', mark: 'bg-good/20' },
  unclear: { name: 'Unclear', fill: 'bg-warning', ink: 'text-warning-ink', onFill: 'text-black', tint: 'bg-warning/18', mark: 'bg-warning/30' },
  blocked: { name: 'Blocked', fill: 'bg-critical', ink: 'text-critical-ink', onFill: 'text-white', tint: 'bg-critical/12', mark: 'bg-critical/20' },
}

/** A link from data (search results, job boards) only if it is http or https, so it can never run script. */
export function safeHref(url: string | null | undefined): string | undefined {
  try {
    const parsed = new URL(url ?? '')
    return parsed.protocol === 'https:' || parsed.protocol === 'http:' ? parsed.href : undefined
  } catch {
    return undefined
  }
}

export const labelName = (label: Label) => LABEL_STYLE[label].name
export const labelInk = (label: Label) => LABEL_STYLE[label].ink

export const SIGNAL_NAMES: Record<string, string> = {
  sponsorship_offered: 'Sponsorship offered',
  no_sponsorship: 'No sponsorship',
  us_citizens_only: 'U.S. citizens only',
  security_clearance: 'Security clearance',
  export_control: 'Export control',
  citizens_or_permanent_residents: 'Citizens or permanent residents',
  e_verify: 'E-Verify',
}

export function headline(label: Label, status: Status): string {
  const who = statusInfo(status).reader
  if (label === 'clear') return `Open to ${who}`
  if (label === 'blocked') return `Not open to ${who}`
  return `The posting doesn't settle it for ${who}`
}

/** Fade sections up as they scroll into view: every [data-reveal] element gets .shown once seen. */
export function useReveal(deps: unknown[] = []) {
  useEffect(() => {
    const targets = document.querySelectorAll<HTMLElement>('[data-reveal]:not(.shown)')
    if (!('IntersectionObserver' in window)) {
      targets.forEach((t) => t.classList.add('shown'))
      return
    }
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue
          entry.target.classList.add('shown')
          observer.unobserve(entry.target)
        }
      },
      { threshold: 0.12 },
    )
    targets.forEach((t) => observer.observe(t))
    return () => observer.disconnect()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
}

/** One value kept in the page URL, so a link reopens the same view. */
export function useUrlParam<T extends string>(name: string, fallback: T, allowed?: readonly T[]) {
  const read = useCallback(() => {
    const value = new URLSearchParams(window.location.search).get(name) as T | null
    return value && (!allowed || allowed.includes(value)) ? value : fallback
  }, [name, fallback, allowed])
  const [value, setValue] = useState<T>(read)

  useEffect(() => {
    const onPop = () => setValue(read())
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [read])

  const update = useCallback(
    (next: T | null) => {
      const params = new URLSearchParams(window.location.search)
      if (next === null || next === fallback) params.delete(name)
      else params.set(name, next)
      const query = params.toString()
      window.history.replaceState(null, '', query ? `?${query}` : window.location.pathname)
      setValue(next ?? fallback)
    },
    [name, fallback],
  )
  return [value, update] as const
}

type Segment = { text: string; signal?: Signal; deciding?: boolean }

/** Split the posting into plain text and quoted signals. Matching ignores case and spacing, like the backend's check. */
export function highlight(text: string, signals: Signal[], deciding: Signal[]): Segment[] {
  const spans: { start: number; end: number; signal: Signal; deciding: boolean }[] = []
  for (const signal of signals) {
    const cleaned = signal.quote.trim().replace(/^["“']+|["”']+$/g, '').replace(/\.$/, '')
    if (!cleaned) continue
    const pattern = cleaned.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\s+/g, '\\s+')
    const match = new RegExp(pattern, 'i').exec(text)
    if (!match) continue
    const isDeciding = deciding.some((d) => d.quote === signal.quote && d.type === signal.type)
    spans.push({ start: match.index, end: match.index + match[0].length, signal, deciding: isDeciding })
  }
  spans.sort((a, b) => a.start - b.start)
  const segments: Segment[] = []
  let cursor = 0
  for (const span of spans) {
    if (span.start < cursor) continue // overlapping quotes: keep the first
    if (span.start > cursor) segments.push({ text: text.slice(cursor, span.start) })
    segments.push({ text: text.slice(span.start, span.end), signal: span.signal, deciding: span.deciding })
    cursor = span.end
  }
  if (cursor < text.length) segments.push({ text: text.slice(cursor) })
  return segments
}
