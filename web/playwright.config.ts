import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { defineConfig, devices } from '@playwright/test'

// End-to-end tests: the real API on the fake model (no credits) and the Vite dev server, driven in
// the installed Microsoft Edge. Run with `npm run test:e2e`.
const WEB = 'http://localhost:5175'

export default defineConfig({
  testDir: 'e2e',
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  use: { baseURL: WEB, channel: 'msedge', trace: 'retain-on-failure' },
  projects: [
    { name: 'desktop', use: { viewport: { width: 1280, height: 900 } } },
    { name: 'phone', use: { ...devices['Pixel 7'], channel: 'msedge' }, grep: /@phone/ },
  ],
  webServer: [
    {
      command: 'uv run uvicorn app.main:app --port 8000',
      cwd: '../backend',
      url: 'http://localhost:8000/health',
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        MODEL_BACKEND: 'fake',
        FAKE_LATENCY: '0.05',
        LOG_PATH: join(tmpdir(), 'sponsorlens-e2e.jsonl'),
        HOURLY_REQUESTS: '1000',
        LIVE_UNTIL: '2099-12-31',
        // Overrides any real key in .env, so a test never spends Tavily credits.
        TAVILY_API_KEY: 'disabled-in-e2e-tests',
      },
    },
    { command: 'npx vite --port 5175 --strictPort', url: WEB, reuseExistingServer: false, timeout: 120_000 },
  ],
})
