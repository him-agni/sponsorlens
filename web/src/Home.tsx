import type { ReactNode } from 'react'
import type { Status } from './api'
import { BoardScan } from './BoardScan'
import { CheckView } from './CheckView'
import { LabelIcon, StatusPicker } from './components'
import { useReveal } from './lib'

// What SponsorLens looks for, floating around the hero in place of photos.
const ORBIT = [
  { text: 'H-1B sponsorship', x: '2%', y: '42%', delay: '0s' },
  { text: 'OPT / STEM OPT', x: '13%', y: '22%', delay: '1.2s' },
  { text: 'Security clearance', x: '33%', y: '2%', delay: '2.1s' },
  { text: 'E-Verify', x: '62%', y: '4%', delay: '0.6s' },
  { text: 'Export control', x: '78%', y: '24%', delay: '1.8s' },
  { text: 'Green card', x: '86%', y: '44%', delay: '0.9s' },
]
const SITES = ['LinkedIn', 'Greenhouse', 'Lever', 'Wellfound', 'Company careers pages']

const STEPS: { title: string; body: string; icon: ReactNode }[] = [
  {
    title: 'Pick your status',
    body: 'EAD, OPT or STEM OPT, needs H-1B sponsorship, or green card. You can switch any time; the answer updates at once.',
    icon: <path d="M8 2.5l4.5 2v3.2c0 2.8-1.9 5-4.5 5.8-2.6-.8-4.5-3-4.5-5.8V4.5z M6 8l1.5 1.5L10.5 6.5" />,
  },
  {
    title: 'Paste a job',
    body: 'The description, or a link from LinkedIn, Greenhouse, Lever or a careers page. Or scan a whole Greenhouse board.',
    icon: <path d="M5.5 3.5h-1a1 1 0 00-1 1v8a1 1 0 001 1h7a1 1 0 001-1v-8a1 1 0 00-1-1h-1M6 2.5h4v2H6zM6 8h4M6 10.5h3" />,
  },
  {
    title: 'Read your answer',
    body: 'Clear, Unclear or Blocked, with the exact lines that decide it, plus location, experience and salary at a glance.',
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
    q: 'Can it be wrong?',
    a: 'Yes, so every verdict quotes the exact lines it used. It is information, not legal advice.',
  },
  {
    q: 'Which links work?',
    a: 'LinkedIn, Greenhouse, Lever, Wellfound and most careers pages. Board scans work for Greenhouse.',
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
        intro="Paste a company's Greenhouse board and every US job comes back sorted: open to you, ask first, or not open."
        tinted
      >
        <BoardScan status={status} live={live} />
      </Section>

      <Section id="how" pill="How it works" title={<>Three steps to <span className="mark">a straight answer</span></>}>
        <ol className="grid gap-4 md:grid-cols-3">
          {STEPS.map((step, i) => (
            <li key={step.title} className="rounded-3xl border border-line bg-surface p-6 transition hover:-translate-y-1 hover:shadow-lg">
              <div className="flex items-center justify-between">
                <span className="flex size-11 items-center justify-center rounded-2xl bg-brand-soft text-accent">
                  <svg viewBox="0 0 16 16" className="size-5" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    {step.icon}
                  </svg>
                </span>
                <span className="text-4xl font-bold text-grid">0{i + 1}</span>
              </div>
              <h3 className="mt-5 text-lg font-semibold">{step.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-ink-2">{step.body}</p>
            </li>
          ))}
        </ol>
      </Section>

      <Section id="faq" pill="FAQ" title={<>Questions, <span className="mark">answered</span></>} tinted>
        <div className="mx-auto grid max-w-3xl gap-3">
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
    <section className="relative overflow-hidden pt-14 pb-10 text-center sm:pt-20">
      <div className="mx-auto max-w-5xl px-4">
        <p className="mx-auto inline-flex animate-rise items-center gap-2 rounded-full border border-line bg-surface px-3 py-1 text-xs text-ink-2">
          <span className="size-1.5 rounded-full bg-good" aria-hidden="true" />
          For H-1B, OPT, EAD and green card holders
        </p>
        <h1 className="mx-auto mt-5 max-w-4xl animate-rise text-4xl leading-[1.2] font-bold tracking-tight sm:text-6xl">
          Is this job open to <span className="mark">your work status?</span>
        </h1>
        <p className="mx-auto mt-5 max-w-2xl animate-rise text-lg text-ink-2 [animation-delay:150ms]">
          SponsorLens reads any US job posting and tells you in seconds whether you can apply, quoting the exact lines that decide it.
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

      {/* The product instead of photos: what it looks for, orbiting three example verdicts. */}
      <div className="relative mx-auto mt-10 h-52 max-w-4xl px-4 sm:mt-12 sm:h-80" aria-hidden="true">
        <div className="absolute inset-x-6 top-4 bottom-0 rounded-t-full border-x border-t border-dashed border-axis sm:top-10" />
        <div className="absolute inset-x-24 top-24 bottom-0 hidden rounded-t-full border-x border-t border-dashed border-grid sm:block" />
        {ORBIT.map((chip) => (
          <span
            key={chip.text}
            className="absolute hidden animate-float items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1.5 text-xs font-medium shadow-sm sm:inline-flex"
            style={{ left: chip.x, top: chip.y, animationDelay: chip.delay }}
          >
            <span className="size-1.5 rounded-full bg-brand" />
            {chip.text}
          </span>
        ))}
        <div className="absolute inset-x-0 bottom-0 flex items-end justify-center gap-3 px-4 sm:gap-5">
          <MiniVerdict label="clear" title="Open to OPT" quote="We sponsor H-1B for this role" className="hidden -rotate-6 sm:block [animation-delay:350ms]" />
          <MiniVerdict label="blocked" title="Not open to H-1B" quote="Active TS/SCI clearance required" className="z-10 scale-105 [animation-delay:200ms]" />
          <MiniVerdict label="unclear" title="Ask the recruiter" quote="The posting says nothing about visas" className="hidden rotate-6 sm:block [animation-delay:500ms]" />
        </div>
      </div>
    </section>
  )
}

function MiniVerdict({ label, title, quote, className = '' }: { label: 'clear' | 'unclear' | 'blocked'; title: string; quote: string; className?: string }) {
  const tint = { clear: 'bg-good/12', unclear: 'bg-warning/18', blocked: 'bg-critical/12' }[label]
  const name = { clear: 'Clear', unclear: 'Unclear', blocked: 'Blocked' }[label]
  return (
    <div className={`w-56 animate-rise rounded-3xl border border-line bg-surface p-2 text-left shadow-xl ${className}`}>
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
    <section id={id} className={`scroll-mt-16 py-16 sm:py-20 ${tinted ? 'bg-tint' : ''}`}>
      <div className="mx-auto max-w-5xl px-4" data-reveal>
        <div className="text-center">
          <span className="inline-block rounded-full border border-line bg-surface px-4 py-1 text-sm">{pill}</span>
          <h2 className="mx-auto mt-4 max-w-3xl text-3xl leading-tight font-bold tracking-tight sm:text-4xl">{title}</h2>
          {intro && <p className="mx-auto mt-3 max-w-2xl text-ink-2">{intro}</p>}
        </div>
        <div className="mt-10">{children}</div>
      </div>
    </section>
  )
}
