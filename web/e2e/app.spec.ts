import { type Page, expect, test } from '@playwright/test'

// The fake model reads "not sponsor" as no sponsorship, so this posting is Blocked for H-1B and
// Clear for EAD, with no credits spent.
const POSTING = `Backend Engineer at Acme Robotics, Austin, TX.
You will build APIs in Python. 3+ years of experience required.
We do not sponsor visas for this role.`

function watchErrors(page: Page): string[] {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('console', (message) => message.type() === 'error' && errors.push(message.text()))
  return errors
}

test('the home page explains itself and shows an example answer @phone', async ({ page }) => {
  const errors = watchErrors(page)
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Is this job open to')
  await expect(page.getByText('Example answer for a sample posting')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Not open to people who need H-1B sponsorship' })).toBeVisible()
  // Nothing spills sideways, on a phone or a desktop.
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  expect(overflow).toBeLessThanOrEqual(0)
  expect(errors).toEqual([])
})

test('checking a pasted posting gives a verdict per status, and Start over clears it', async ({ page }) => {
  const errors = watchErrors(page)
  await page.goto('/')
  const box = page.getByLabel('Paste a job description or its link')
  await box.fill(POSTING)
  await page.getByRole('button', { name: 'Check posting' }).click()

  await expect(page.getByRole('heading', { name: 'Not open to people who need H-1B sponsorship' })).toBeVisible()
  await expect(page.getByText('Example answer')).toHaveCount(0)
  await expect(page.locator('mark').filter({ hasText: 'We do not sponsor visas' })).toBeVisible()

  // Switching status answers at once, from the same check.
  await page.getByRole('radio', { name: 'EAD' }).click()
  await expect(page.getByRole('heading', { name: 'Open to EAD holders' })).toBeVisible()
  await expect(page).toHaveURL(/status=ead/)

  await page.getByRole('button', { name: 'Start over' }).click()
  await expect(box).toHaveValue('')
  expect(errors).toEqual([])
})

test('a pasted link is read into the box, then checked', async ({ page }) => {
  // The link reader calls Tavily; answer it here so the test is free and offline.
  await page.route('**/api/read-link', (route) =>
    route.fulfill({ json: { url: 'https://jobs.lever.co/acme/1', title: null, company: null, text: POSTING } }),
  )
  await page.goto('/')
  await page.getByLabel('Paste a job description or its link').fill('https://jobs.lever.co/acme/1')
  await page.getByRole('button', { name: 'Check link' }).click()
  await expect(page.getByLabel('Paste a job description or its link')).toHaveValue(POSTING)
  await expect(page.getByRole('link', { name: 'jobs.lever.co' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Not open to people who need H-1B sponsorship' })).toBeVisible()
})

test('scanning a board shows job cards, filtered by verdict', async ({ page }) => {
  // The scan reads a live Greenhouse board; answer it with two jobs so the test is offline.
  const rows = [
    { title: 'Rocket Engineer', label: 'blocked', type: 'export_control', quote: 'Applicants must be U.S. persons' },
    { title: 'Data Analyst', label: 'clear', type: 'sponsorship_offered', quote: 'We sponsor H-1B visas' },
  ].map((job, i) => ({
    job_id: `scan1:greenhouse:acme:${i}`,
    source: `greenhouse:acme:${i}`,
    company: 'Acme',
    company_name: 'Acme',
    title: job.title,
    url: `https://job-boards.greenhouse.io/acme/jobs/${i}`,
    location: 'Austin, TX',
    shard: 0,
    state: 'done',
    error: null,
    labels: null,
    verdict: {
      status: 'h1b',
      label: job.label,
      deciding: [{ type: job.type, quote: job.quote, reading: '' }],
      notes: [],
      next_step: 'Next step text.',
    },
  }))
  await page.route('**/api/scan', (route) => route.fulfill({ status: 202, json: { id: 'scan1', company: 'acme', found: 2, scanning: 2 } }))
  await page.route('**/api/batch/scan1*', (route) =>
    route.fulfill({ json: { id: 'scan1', status: 'h1b', finished: true, progress: { total: 2, done: 2 }, items: rows } }),
  )
  await page.goto('/#scan')
  await page.getByLabel('Company careers page or Greenhouse board link').fill('https://www.acme.com/careers')
  await page.getByRole('button', { name: 'Scan board' }).click()

  await expect(page.getByRole('heading', { name: 'acme jobs' })).toBeVisible()
  await expect(page.getByRole('article')).toHaveCount(2)
  await page.getByRole('tab', { name: /Open to you/ }).click()
  await expect(page.getByRole('article')).toHaveCount(1)
  await expect(page.getByRole('article')).toContainText('Data Analyst')
  await page.getByRole('button', { name: 'Details' }).click()
  await expect(page.getByText('“We sponsor H-1B visas”')).toBeVisible()
})

test('the theme switch applies at once and is remembered', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('radio', { name: 'Dark' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.getByRole('radio', { name: 'Match device' }).click()
  await expect(page.locator('html')).not.toHaveAttribute('data-theme', /.+/)
})

test('Under the hood shows the live engine and the recorded run, and Back returns', async ({ page }) => {
  const errors = watchErrors(page)
  await page.goto('/')
  await page.getByRole('button', { name: 'Under the hood' }).click()
  await expect(page.getByRole('heading', { name: 'The engine, live' })).toBeVisible()
  await expect(page.getByText('Postings done')).toBeVisible()
  await page.getByRole('button', { name: 'The 200-job run' }).click()
  await expect(page).toHaveURL(/view=batch/)
  await page.getByRole('button', { name: '← Back' }).click()
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Is this job open to')
  expect(errors).toEqual([])
})

test('the FAQ answers open on click', async ({ page }) => {
  await page.goto('/#faq')
  const question = page.getByText('Do you store the jobs I paste?')
  await question.click()
  await expect(page.getByText('No. The posting text is never saved.')).toBeVisible()
})

test('after the demo ends, the site shows its recordings and says why @phone', async ({ page }) => {
  await page.route('**/health', (route) => route.fulfill({ json: { status: 'ok', live: false, live_batches: false } }))
  await page.goto('/')
  await expect(page.getByRole('status')).toContainText('The live demo ended after hackathon judging')
  await expect(page.getByRole('button', { name: 'Check posting' })).toBeDisabled()
  await expect(page.getByText('Example answer for a sample posting')).toBeVisible()
})
