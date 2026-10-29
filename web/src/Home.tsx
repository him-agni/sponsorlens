import { type ReactNode, useState } from 'react'
import type { Label, Status } from './api'
import { BoardScan } from './BoardScan'
import { CheckView } from './CheckView'
import { LabelIcon, StatusPicker } from './components'
import { LABEL_STYLE, useReveal } from './lib'

// What SponsorLens looks for, floating around the hero in place of photos; each explains itself on
// hover or focus.
const ORBIT = [
  { text: 'H-1B sponsorship', meaning: 'The employer files and pays for your H-1B work visa.', x: '2%', y: '42%', delay: '0s' },
  { text: 'OPT / STEM OPT', meaning: 'Work permission for F-1 students after graduation, for 1 to 3 years.', x: '13%', y: '22%', delay: '1.2s' },
  { text: 'Security clearance', meaning: 'Government approval to handle classified work; almost always U.S. citizens only.', x: '33%', y: '2%', delay: '2.1s' },
  { text: 'E-Verify', meaning: "A government check that a new hire may work in the U.S. A STEM OPT extension needs an employer that uses it.", x: '62%', y: '4%', delay: '0.6s' },
  { text: 'Export control', meaning: 'Some technology may only be shared with U.S. citizens or green card holders, which can rule out visas.', x: '78%', y: '24%', delay: '1.8s' },
  { text: 'Green card', meaning: 'Permanent residence. Most jobs are open to green card holders.', x: '86%', y: '44%', delay: '0.9s' },
]
const SITES = ['LinkedIn', 'Greenhouse', 'Lever', 'Ashby', 'Wellfound', 'Company careers pages']

const STEPS: { title: string; body: string; icon: ReactNode }[] = [
  {
    title: 'Pick your status',
    body: 'EAD, OPT, H-1B or green card. Switch any time.',
    icon: <path d="M8 2.5l4.5 2v3.2c0 2.8-1.9 5-4.5 5.8-2.6-.8-4.5-3-4.5-5.8V4.5z M6 8l1.5 1.5L10.5 6.5" />,
  },
  {
    title: 'Paste a job',
    body: 'Its description or link, or a whole careers page.',
    icon: <path d="M5.5 3.5h-1a1 1 0 00-1 1v8a1 1 0 001 1h7a1 1 0 001-1v-8a1 1 0 00-1-1h-1M6 2.5h4v2H6zM6 8h4M6 10.5h3" />,
  },
  {
    title: 'Read your answer',
    body: 'Clear, Unclear or Blocked, with the lines that prove it.',
    icon: <path d="M2.5 8s2-4 5.5-4 5.5 4 5.5 4-2 4-5.5 4-5.5-4-5.5-4z M8 9.5a1.5 1.5 0 100-3 1.5 1.5 0 000 3z" />,
  },
]

const FAQS = [
  {
    q: 'What does SponsorLens check?',
    a: 'Whether a job sponsors visas or requires citizenship, a clearance or export-control status. Plus location, experience and salary.',
  },
  {
    q: 'What do Clear, Unclear and Blocked mean?',
    a: "Clear: nothing stops you. Blocked: the posting rules you out. Unclear: it doesn't say, so ask the recruiter.",
  },
  {
    q: 'What are E-Verify, export control and a security clearance?',
    a: 'E-Verify: a government check that a new hire may work in the U.S.; STEM OPT needs an employer that uses it. Export control usually means U.S. citizens and green card holders only; a clearance, U.S. citizens only.',
  },
  {
    q: 'Can it be wrong?',
    a: 'Yes, so every verdict quotes the exact lines it used. It is information, not legal advice.',
  },
  {
    q: 'Which links work?',
    a: 'LinkedIn, Greenhouse, Lever, Wellfound and most careers pages. Board scans work for companies on Greenhouse, Lever or Ashby.',
  },
  {
    q: 'Do you store the jobs I paste?',
    a: 'No. The posting text is never saved.',
  },
  {
    q: 'Why did my first check take a while?',
    a: 'The free server sleeps when idle and takes about a minute to wake. After that, checks take 10 to 30 seconds.',
  },
  {
    q: 'What is it built with?',
    a: 'NVIDIA Nemotron on Nebius Token Factory, Tavily, and a hand-built engine. See Under the hood.',
  },
]

export function Home({ status, onStatus, live }: { status: Status; onStatus: (s: Status) => void; live: boolean }) {
  useReveal()
  return (
    <>
      <Hero />
      <Marquee />

      <Section id="check" pill="Check a job" title={<>Paste a job. <span className="mark">Get your answer.</span></>}>
        <div className="mb-6">
          <p className="mb-1.5 text-sm font-medium">Your work status</p>
          <StatusPicker value={status} onChange={onStatus} />
        </div>
        <CheckView status={status} onStatus={onStatus} live={live} />
      </Section>

      <Section
        id="scan"
        pill="Scan a board"
        title={<>Scan a whole job board. <span className="mark">See where to apply.</span></>}
        intro="Paste a company's careers page and every US job comes back sorted: open to you, ask first, or not open."
        tinted
      >
        <BoardScan status={status} live={live} />
      </Section>

      <Section id="how" pill="How it works" title={<>Three steps to <span className="mark">a straight answer</span></>}>
        {/* A compact row per step on phones (icon beside the text); cards with big numbers on larger screens. */}
        <ol className="grid grid-cols-1 gap-3 sm:gap-4 md:grid-cols-3">
          {STEPS.map((step, i) => (
            <li
              key={step.title}
              className="flex items-start gap-4 rounded-3xl border border-line bg-surface p-4 transition hover:-translate-y-1 hover:shadow-lg sm:block sm:p-6"
            >
              <div className="flex shrink-0 items-center justify-between">
                <span className="flex size-11 items-center justify-center rounded-2xl bg-brand-soft text-accent">
                  <svg viewBox="0 0 16 16" className="size-5" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    {step.icon}
                  </svg>
                </span>
                <span className="hidden text-4xl font-bold text-grid sm:inline">0{i + 1}</span>
              </div>
              <div>
                <h3 className="font-semibold sm:mt-5 sm:text-lg">{step.title}</h3>
                <p className="mt-1 text-sm leading-relaxed text-ink-2 sm:mt-1.5">{step.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </Section>

      <Section id="faq" pill="FAQ" title={<>Questions, <span className="mark">answered</span></>} tinted>
        <div className="mx-auto grid grid-cols-1 max-w-3xl gap-3">
          {FAQS.map((item) => (
            <details key={item.q} className="group rounded-2xl border border-line bg-surface px-5 py-4 open:shadow-sm">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-semibold [&::-webkit-details-marker]:hidden">
                {item.q}
                <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-brand-soft text-accent transition group-open:rotate-45" aria-hidden="true">
                  +
                </span>
              </summary>
              <p className="mt-3 text-sm leading-relaxed text-ink-2">{item.a}</p>
            </details>
          ))}
        </div>
      </Section>
    </>
  )
}

function Hero() {
  return (
    <section className="relative overflow-hidden pt-10 pb-10 text-center sm:pt-20">
      <div className="mx-auto max-w-5xl px-4">
        <p className="mx-auto inline-flex animate-rise items-center gap-2 rounded-full border border-line bg-surface px-3 py-1 text-xs text-ink-2">
          <span className="size-1.5 rounded-full bg-good" aria-hidden="true" />
          For H-1B, OPT, EAD and green card holders
        </p>
        <h1 className="mx-auto mt-5 max-w-4xl animate-rise text-4xl leading-[1.2] font-bold tracking-tight sm:text-6xl">
          Is this job open to <span className="mark">your work status?</span>
        </h1>
        <p className="mx-auto mt-5 max-w-2xl animate-rise text-lg text-ink-2 [animation-delay:150ms]">
          <span className="sm:hidden">Paste a job. Get a straight answer, with proof.</span>
          <span className="hidden sm:inline">
            SponsorLens reads any US job posting and tells you in seconds whether you can apply, quoting the exact lines that decide it.
          </span>
        </p>
        <div className="mt-7 flex animate-rise flex-wrap justify-center gap-3 [animation-delay:250ms]">
          <a href="#check" className="rounded-xl bg-brand px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-brand/25 transition hover:brightness-110">
            Check a job
          </a>
          <a href="#scan" className="rounded-xl border border-line bg-surface px-5 py-3 text-sm font-semibold transition hover:bg-line">
            Scan a job board
          </a>
        </div>
      </div>

      {/* Phones: the terms as chips that explain themselves when tapped, then the verdicts as a fanned deck. */}
      <div className="mx-auto mt-10 max-w-md px-4 sm:hidden">
        <TermChips />
        <div aria-hidden="true" className="mt-6 flex flex-col items-center">
          <MiniVerdict label="clear" title="Open to OPT" quote="We sponsor H-1B for this role" className="w-[min(16rem,85%)] -rotate-3 [animation-delay:150ms]" />
          <MiniVerdict label="unclear" title="Ask the recruiter" quote="The posting says nothing about visas" className="-mt-20 w-[min(16rem,85%)] translate-x-3 rotate-2 [animation-delay:300ms]" />
          <MiniVerdict label="blocked" title="Not open to H-1B" quote="Active TS/SCI clearance required" className="-mt-[6.5rem] w-[min(16rem,85%)] -translate-x-2 -rotate-1 [animation-delay:450ms]" />
        </div>
      </div>

      {/* Larger screens: what it looks for, orbiting three example verdicts. */}
      <div className="relative mx-auto mt-12 hidden h-80 max-w-4xl px-4 sm:block">
        <div aria-hidden="true" className="absolute inset-x-6 top-10 bottom-0 rounded-t-full border-x border-t border-dashed border-axis" />
        <div aria-hidden="true" className="absolute inset-x-24 top-24 bottom-0 rounded-t-full border-x border-t border-dashed border-grid" />
        {ORBIT.map((chip) => (
          <button
            key={chip.text}
            type="button"
            aria-label={chip.text}
            aria-describedby={`orbit-${chip.text}`}
            className="group absolute inline-flex animate-float items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1.5 text-xs font-medium shadow-sm hover:z-20 hover:border-brand hover:[animation-play-state:paused] focus-visible:z-20 focus-visible:[animation-play-state:paused]"
            style={{ left: chip.x, top: chip.y, animationDelay: chip.delay }}
          >
            <span className="size-1.5 rounded-full bg-brand" aria-hidden="true" />
            {chip.text}
            <span
              id={`orbit-${chip.text}`}
              role="tooltip"
              className={`pointer-events-none absolute top-full mt-2 w-60 rounded-xl bg-ink p-3 text-left text-xs leading-snug font-normal text-page opacity-0 shadow-xl transition group-hover:opacity-100 group-focus-visible:opacity-100 ${
                parseInt(chip.x) > 60 ? 'right-0' : 'left-0'
              }`}
            >
              {chip.meaning}
            </span>
          </button>
        ))}
        <div aria-hidden="true" className="absolute inset-x-0 bottom-0 flex items-end justify-center gap-5 px-4">
          <MiniVerdict label="clear" title="Open to OPT" quote="We sponsor H-1B for this role" className="w-56 -rotate-6 [animation-delay:350ms]" />
          <MiniVerdict label="blocked" title="Not open to H-1B" quote="Active TS/SCI clearance required" className="z-10 w-56 scale-105 [animation-delay:200ms]" />
          <MiniVerdict label="unclear" title="Ask the recruiter" quote="The posting says nothing about visas" className="w-56 rotate-6 [animation-delay:500ms]" />
        </div>
      </div>
    </section>
  )
}

/** On phones, where nothing can be hovered: tap a term to read its meaning under the row. */
function TermChips() {
  const [open, setOpen] = useState<string | null>(null)
  const term = ORBIT.find((chip) => chip.text === open)
  return (
    <div>
      <div className="flex flex-wrap justify-center gap-2">
        {ORBIT.map((chip) => (
          <button
            key={chip.text}
            type="button"
            aria-pressed={open === chip.text}
            onClick={() => setOpen(open === chip.text ? null : chip.text)}
            className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium ${
              open === chip.text ? 'border-brand bg-brand-soft' : 'border-line bg-surface'
            }`}
          >
            <span className="size-1.5 rounded-full bg-brand" aria-hidden="true" />
            {chip.text}
          </button>
        ))}
      </div>
      <p aria-live="polite" className="mt-3 min-h-10 text-sm text-ink-2">
        {term ? term.meaning : 'Tap a term to see what it means.'}
      </p>
    </div>
  )
}

function MiniVerdict({ label, title, quote, className = '' }: { label: Label; title: string; quote: string; className?: string }) {
  const { tint, name } = LABEL_STYLE[label]
  return (
    <div className={`animate-rise rounded-3xl border border-line bg-surface p-2 text-left shadow-xl ${className}`}>
      <div className={`rounded-2xl p-4 ${tint}`}>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-surface px-2.5 py-1 text-xs font-semibold">
          <LabelIcon label={label} className="size-3.5" />
          {name}
        </span>
        <p className="mt-3 font-semibold">{title}</p>
        <p className="mt-2 border-l-2 border-ink/20 pl-2 text-xs text-ink-2">“{quote}”</p>
      </div>
    </div>
  )
}

function Marquee() {
  const row = [...SITES, ...SITES]
  return (
    <div className="border-y border-line py-5">
      <p className="text-center text-sm text-ink-2">Paste links from</p>
      <div className="relative mt-3 overflow-hidden [mask-image:linear-gradient(90deg,transparent,black_12%,black_88%,transparent)]">
        <div className="flex w-max animate-marquee gap-12 pr-12">
          {[...row, ...row].map((site, i) => (
            <span key={i} className="text-lg font-semibold whitespace-nowrap text-muted">
              {site}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}

function Section({
  id,
  pill,
  title,
  intro,
  tinted = false,
  children,
}: {
  id: string
  pill: string
  title: ReactNode
  intro?: string
  tinted?: boolean
  children: ReactNode
}) {
  return (
    <section id={id} className={`scroll-mt-16 py-12 sm:py-20 ${tinted ? 'bg-tint' : ''}`}>
      <div className="mx-auto max-w-5xl px-4" data-reveal>
        <div className="text-center">
          <span className="inline-block rounded-full border border-line bg-surface px-4 py-1 text-sm">{pill}</span>
          <h2 className="mx-auto mt-4 max-w-3xl text-3xl leading-tight font-bold tracking-tight sm:text-4xl">{title}</h2>
          {intro && <p className="mx-auto mt-3 hidden max-w-2xl text-ink-2 sm:block">{intro}</p>}
        </div>
        <div className="mt-8 sm:mt-10">{children}</div>
      </div>
    </section>
  )
}
