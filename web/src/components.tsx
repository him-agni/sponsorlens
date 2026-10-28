import { useState, type ReactNode } from 'react'
import type { Label, Status } from './api'
import type { EngineState } from './engine'
import { LABEL_STYLE, STATUSES } from './lib'

export function LabelIcon({ label, className = 'size-4' }: { label: Label; className?: string }) {
  return (
    <svg viewBox="0 0 16 16" className={className} aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8">
      <circle cx="8" cy="8" r="6.5" />
      {label === 'clear' && <path d="M5 8.2l2 2 4-4.4" strokeLinecap="round" strokeLinejoin="round" />}
      {label === 'blocked' && <path d="M3.6 12.4l8.8-8.8" strokeLinecap="round" />}
      {label === 'unclear' && (
        <>
          <path d="M6.3 6.2a1.8 1.8 0 113 1.4c-.7.5-1.3.9-1.3 1.7" strokeLinecap="round" />
          <circle cx="8" cy="11.3" r=".5" fill="currentColor" stroke="none" />
        </>
      )}
    </svg>
  )
}

export function VerdictBadge({ label, size = 'sm' }: { label: Label; size?: 'sm' | 'lg' }) {
  const style = LABEL_STYLE[label]
  const big = size === 'lg'
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-medium ${style.fill} ${style.onFill} ${
        big ? 'px-3 py-1 text-base' : 'px-2 py-0.5 text-xs'
      }`}
    >
      <LabelIcon label={label} className={big ? 'size-5' : 'size-3.5'} />
      {style.name}
    </span>
  )
}

export function StatusPicker({ value, onChange }: { value: Status; onChange: (s: Status) => void }) {
  return (
    <div role="radiogroup" aria-label="Your work-authorization status" className="grid grid-cols-2 gap-1 rounded-xl border border-line bg-surface p-1 sm:inline-grid sm:grid-cols-4">
      {STATUSES.map((s) => (
        <button
          key={s.id}
          role="radio"
          aria-checked={value === s.id}
          onClick={() => onChange(s.id)}
          className={`rounded-lg px-3 py-1.5 text-sm transition-colors ${
            value === s.id ? 'bg-ink font-medium text-page' : 'text-ink-2 hover:bg-line'
          }`}
        >
          {s.short}
        </button>
      ))}
    </div>
  )
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-2xl border border-line bg-surface p-5 ${className}`}>{children}</section>
}

export function Spinner() {
  return <span className="inline-block size-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true" />
}

type Theme = 'auto' | 'light' | 'dark'
const THEMES: { id: Theme; name: string; icon: ReactNode }[] = [
  { id: 'auto', name: 'Match device', icon: <path d="M2.5 3.5h11v7h-11zM6 13.5h4M8 10.5v3" /> },
  { id: 'light', name: 'Light', icon: <><circle cx="8" cy="8" r="2.8" /><path d="M8 1.5v1.5M8 13v1.5M1.5 8H3M13 8h1.5M3.4 3.4l1 1M11.6 11.6l1 1M3.4 12.6l1-1M11.6 4.4l1-1" /></> },
  { id: 'dark', name: 'Dark', icon: <path d="M12.8 10.2A5.5 5.5 0 015.8 3.2a5.5 5.5 0 107 7z" /> },
]

function savedTheme(): Theme {
  try {
    const saved = localStorage.getItem('theme')
    return saved === 'light' || saved === 'dark' ? saved : 'auto'
  } catch {
    return 'auto'
  }
}

function applyTheme(theme: Theme) {
  const root = document.documentElement
  if (theme === 'auto') delete root.dataset.theme
  else root.dataset.theme = theme
  try {
    if (theme === 'auto') localStorage.removeItem('theme')
    else localStorage.setItem('theme', theme)
  } catch {
    // Storage can be blocked; the choice still holds for this visit.
  }
}

/** Light, dark, or the device's setting. index.html applies the saved choice before first paint. */
export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(savedTheme)

  function choose(next: Theme) {
    setTheme(next)
    applyTheme(next)
  }

  return (
    <div role="radiogroup" aria-label="Color theme" className="inline-flex rounded-lg border border-line bg-surface p-0.5">
      {THEMES.map((t) => (
        <button
          key={t.id}
          role="radio"
          aria-checked={theme === t.id}
          aria-label={t.name}
          title={t.name}
          onClick={() => choose(t.id)}
          className={`rounded-md p-1.5 ${theme === t.id ? 'bg-ink text-page' : 'text-ink-2 hover:bg-line'}`}
        >
          <svg viewBox="0 0 16 16" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            {t.icon}
          </svg>
        </button>
      ))}
    </div>
  )
}

export function EngineBanner({ state, recorded, backend }: { state: EngineState; recorded?: string; backend?: string }) {
  if (state === 'live' || state === 'checking') return null
  const sample = recorded ? `a saved sample run (${backend === 'fake' ? 'fake model, ' : ''}recorded ${recorded})` : 'a saved sample run'
  const message =
    state === 'waking'
      ? `Waking the engine. The free server sleeps when idle and takes about a minute; meanwhile you are looking at ${sample}.`
      : state === 'ended'
        ? `The live demo ended after hackathon judging, so you are looking at ${sample}. The code is on GitHub.`
        : state === 'no-engine'
          ? `The live engine is paused, so you are looking at ${sample}.`
          : `The engine can't be reached right now, so you are looking at ${sample}.`
  return (
    <div role="status" className="border-b border-line bg-warning/15">
      <p className="mx-auto flex max-w-5xl items-start gap-2 px-4 py-2.5 text-sm text-ink">
        {state === 'waking' ? <Spinner /> : <LabelIcon label="unclear" className="mt-0.5 size-4 shrink-0" />}
        <span>{message}</span>
      </p>
    </div>
  )
}
