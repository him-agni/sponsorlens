import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { vi } from 'vitest'

const PUBLIC = join(import.meta.dirname, '..', '..', 'public')

/** The recorded sample run shipped with the app, as the browser would load it. */
export function sample<T = unknown>(name: 'examples' | 'batch' | 'metrics'): T {
  return JSON.parse(readFileSync(join(PUBLIC, 'sample', `${name}.json`), 'utf-8'))
}

type Answer = unknown | ((init?: RequestInit) => unknown)

/**
 * Replace fetch: /sample/*.json comes from public/, API paths from `api` (a path, or a path with its
 * query, to a JSON body or a function of the request). Anything else is a network error, so a test
 * never reaches a real server. Returns the mock, to inspect the calls.
 */
export function serve(api: Record<string, Answer> = {}) {
  const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), 'http://localhost')
    const sampleName = url.pathname.match(/^\/sample\/(\w+)\.json$/)?.[1]
    if (sampleName) return Response.json(sample(sampleName as 'examples'))
    const answer = api[url.pathname + url.search] ?? api[url.pathname]
    if (answer === undefined) throw new TypeError(`no route for ${url.pathname}`)
    const body = typeof answer === 'function' ? answer(init) : answer
    if (body instanceof Response) return body
    return Response.json(body)
  })
  vi.stubGlobal('fetch', mock)
  return mock
}
