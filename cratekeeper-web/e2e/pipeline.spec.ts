import { test, expect, type Route } from '@playwright/test'

/**
 * Full event-pipeline e2e: walks every step on the EventDetail page, clicks
 * "Run", asserts the correct enqueue POST is made (with the right type and
 * params, including the M4 dry-run toggles), and confirms each job's status
 * card appears.
 *
 * All API/SSE traffic is mocked. Backend is not required.
 */

const EVENT_ID = '22222222-2222-2222-2222-222222222222'

const event = {
  id: EVENT_ID,
  name: 'Pipeline Test Event',
  slug: 'pipeline-test',
  date: '2026-07-15',
  source_playlist_url: 'https://open.spotify.com/playlist/xyz',
  source_playlist_id: 'xyz',
  source_playlist_name: 'Wishes',
  build_mode: 'copy',
  status: 'ready',
  created_at: '2026-04-01T00:00:00Z',
  updated_at: '2026-04-20T00:00:00Z',
  llm_cost_cents: 0,
  llm_token_input: 0,
  llm_token_output: 0,
  llm_token_cache_read: 0,
  llm_token_cache_write: 0,
  track_count: 3,
}

type EnqueuedJob = { id: string; type: string; params: Record<string, unknown> }

type Step = {
  type: string
  label: RegExp
  params?: Record<string, unknown>
  fillByPlaceholder?: { placeholder: string; value: string }[]
  checkDryRun?: boolean
}

/** Order matches STEPS in EventDetail.tsx so we cover the full pipeline. */
const STEPS: Step[] = [
  { type: 'fetch', label: /^Intake$/ },
  { type: 'classify', label: /^Classify$/ },
  { type: 'classify-tags', label: /^Tag \(LLM\)$/ },
  { type: 'scan-incremental', label: /^Scan \(incremental\)$/ },
  {
    type: 'match',
    label: /^Match$/,
    fillByPlaceholder: [{ placeholder: '85', value: '85' }],
    params: { fuzzy_threshold: 85 },
  },
  { type: 'analyze-mood', label: /^Analyze$/ },
  {
    type: 'apply-tags',
    label: /^Write tags$/,
    checkDryRun: true,
    params: { dry_run: true },
  },
  {
    type: 'undo-tags',
    label: /^Undo last tag write$/,
    checkDryRun: true,
    params: { dry_run: true },
  },
  {
    type: 'build-event',
    label: /^Build event folder$/,
    fillByPlaceholder: [{ placeholder: '~/Music/EventBuilds', value: '/tmp/events' }],
    checkDryRun: true,
    params: { output_dir: '/tmp/events', dry_run: true },
  },
  {
    type: 'build-library',
    label: /^Build library$/,
    fillByPlaceholder: [{ placeholder: '~/Music/Library', value: '/tmp/library' }],
    checkDryRun: true,
    params: { output_dir: '/tmp/library', dry_run: true },
  },
  {
    type: 'sync-spotify',
    label: /Sync . Spotify/,
    fillByPlaceholder: [{ placeholder: '', value: 'My Test Sync' }],
    params: { name: 'My Test Sync' },
  },
  {
    type: 'sync-tidal',
    label: /Sync . Tidal/,
    params: {},
  },
]

async function setupApiMocks(page: import('@playwright/test').Page, enqueued: EnqueuedJob[]) {
  await page.route('**/api/v1/**', async (route: Route) => {
    const req = route.request()
    const url = new URL(req.url())
    const path = url.pathname
    const method = req.method()

    // ---- mutations: enqueue jobs ----
    if (method === 'POST' && path === `/api/v1/events/${EVENT_ID}/jobs`) {
      const body = req.postDataJSON() as { type: string; params: Record<string, unknown> }
      const id = `job-${enqueued.length + 1}`
      enqueued.push({ id, type: body.type, params: body.params })
      const job = {
        id,
        event_id: EVENT_ID,
        type: body.type,
        status: 'succeeded',
        params: body.params,
        result: { ok: true },
        error: null,
        created_at: new Date().toISOString(),
        started_at: new Date().toISOString(),
        finished_at: new Date().toISOString(),
      }
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(job) })
      return
    }

    // ---- single job poll ----
    const jobMatch = path.match(/^\/api\/v1\/jobs\/(job-\d+)$/)
    if (method === 'GET' && jobMatch) {
      const id = jobMatch[1]
      const j = enqueued.find((e) => e.id === id)
      const job = {
        id,
        event_id: EVENT_ID,
        type: j?.type ?? 'unknown',
        status: 'succeeded',
        params: j?.params ?? {},
        result: { ok: true },
        error: null,
        created_at: new Date().toISOString(),
        started_at: new Date().toISOString(),
        finished_at: new Date().toISOString(),
      }
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(job) })
      return
    }

    // ---- job list (per-event) ----
    if (method === 'GET' && path === '/api/v1/jobs') {
      const list = enqueued.map((e) => ({
        id: e.id,
        event_id: EVENT_ID,
        type: e.type,
        status: 'succeeded',
        params: e.params,
        result: { ok: true },
        error: null,
        created_at: new Date().toISOString(),
        started_at: new Date().toISOString(),
        finished_at: new Date().toISOString(),
      }))
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(list) })
      return
    }

    // ---- SSE streams: respond with a closed empty stream so the component
    // falls back to polling and immediately sees `succeeded`.
    if (path.includes('/events/progress') || path.includes('/events/log')) {
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: '',
        headers: { 'cache-control': 'no-cache' },
      })
      return
    }

    // ---- read endpoints used by EventDetail ----
    const fixtures: Record<string, unknown> = {
      [`GET /api/v1/events/${EVENT_ID}`]: event,
      [`GET /api/v1/events/${EVENT_ID}/tracks`]: [],
      [`GET /api/v1/events/${EVENT_ID}/quality-checks`]: { overall: 'pass', checks: [] },
      [`GET /api/v1/events/${EVENT_ID}/builds`]: [],
      [`GET /api/v1/events/${EVENT_ID}/sync-runs`]: [],
      [`GET /api/v1/events/${EVENT_ID}/tidal-urls`]: { urls: {}, count: 0 },
    }
    const key = `${method} ${path}`
    if (fixtures[key] !== undefined) {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(fixtures[key]) })
      return
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: 'null' })
  })
}

test.describe('full event pipeline', () => {
  test('runs every pipeline step and verifies the enqueue payload', async ({ page }) => {
    const enqueued: EnqueuedJob[] = []
    await setupApiMocks(page, enqueued)

    await page.goto(`/events/${EVENT_ID}`)
    await expect(page.getByRole('heading', { name: 'Pipeline Test Event' })).toBeVisible()

    for (const step of STEPS) {
      await test.step(`run "${step.type}"`, async () => {
        // Each step is a `.card` containing an h3 heading with the label.
        const card = page.locator('.card', { has: page.getByRole('heading', { name: step.label, level: 3 }) })
        await expect(card).toHaveCount(1)

        // Fill any text inputs (look up by placeholder; sync-spotify has none
        // so we target the first text input in the card).
        for (const t of step.fillByPlaceholder ?? []) {
          const input = t.placeholder
            ? card.getByPlaceholder(t.placeholder)
            : card.locator('input[type="text"]').first()
          await input.fill(t.value)
        }
        // Tick dry-run if requested.
        if (step.checkDryRun) {
          await card.getByLabel('Dry run', { exact: true }).check()
        }

        const before = enqueued.length
        await card.getByRole('button', { name: /^Run$/ }).click()

        // Wait for the POST to be recorded.
        await expect.poll(() => enqueued.length).toBeGreaterThan(before)

        const last = enqueued[enqueued.length - 1]
        expect(last.type).toBe(step.type)
        if (step.params) expect(last.params).toMatchObject(step.params)

        // The active-job section appears with a "succeeded" badge once polling lands.
        await expect(page.getByRole('heading', { name: /Active job/i })).toBeVisible()
        await expect(page.locator('.tag', { hasText: 'succeeded' }).first()).toBeVisible({ timeout: 5000 })
      })
    }

    // Sanity: every step type is represented in the enqueue history exactly once.
    const types = enqueued.map((e) => e.type).sort()
    expect(types).toEqual(STEPS.map((s) => s.type).sort())
  })
})
