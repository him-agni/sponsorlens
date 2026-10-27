import type { ReactNode } from 'react'
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

export function EngineBanner({ state, recorded, backend }: { state: EngineState; recorded?: string; backend?: string }) {
  if (state === 'live' || state === 'checking') return null
  const sample = recorded ? `a saved sample run (${backend === 'fake' ? 'fake model, ' : ''}recorded ${recorded})` : 'a saved sample run'
  const message =
    state === 'waking'
      ? `Waking the engine. The free server sleeps when idle and takes about a minute; meanwhile you are looking at ${sample}.`
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
