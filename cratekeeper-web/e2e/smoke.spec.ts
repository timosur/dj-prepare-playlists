import { test, expect, type Route } from '@playwright/test'

/**
 * Mocked-API E2E smoke tests for the M4 frontend surfaces.
 *
 * No backend required: every /api/v1/* request is fulfilled with a fixture.
 * These tests verify wiring (routes, nav, forms, data binding) — not
 * end-to-end backend behaviour.
 */

const EVENT_ID = '11111111-1111-1111-1111-111111111111'

const event = {
  id: EVENT_ID,
  name: 'Test Wedding',
  slug: 'test-wedding',
  date: '2026-06-01',
  source_playlist_url: 'https://open.spotify.com/playlist/abc',
  source_playlist_id: 'abc',
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
}

const mockResponses: Record<string, unknown> = {
  'GET /api/v1/events': [event],
  [`GET /api/v1/events/${EVENT_ID}`]: event,
  [`GET /api/v1/events/${EVENT_ID}/tracks`]: [],
  [`GET /api/v1/events/${EVENT_ID}/quality-checks`]: {
    overall: 'pass',
    checks: [
      { name: 'matched', status: 'pass', detail: 'all matched', metric: 100 },
    ],
  },
  'GET /api/v1/jobs': [],
  'GET /api/v1/audit': [
    {
      id: 1,
      ts: '2026-04-23T10:00:00Z',
      actor: 'local',
      action: 'tags.apply',
      target_kind: 'event',
      target_id: EVENT_ID,
      payload: { tracks: 12 },
    },
    {
      id: 2,
      ts: '2026-04-23T10:05:00Z',
      actor: 'local',
      action: 'settings.fs_roots.update',
      target_kind: null,
      target_id: null,
      payload: { roots: ['/Users/test/Music'] },
    },
  ],
  'GET /api/v1/settings': {
    fs_roots: ['/Users/test/Music'],
    anthropic_configured: true,
    spotify_configured: true,
    tidal_configured: true,
    auth_token_set: false,
  },
  'GET /api/v1/settings/anthropic': { has_key: true, model: 'claude-sonnet-4', prompt_caching: true },
  'GET /api/v1/settings/fs-roots': { roots: ['/Users/test/Music'] },
  'GET /api/v1/settings/auth/spotify': { ok: true, user: 'tester' },
  'GET /api/v1/settings/auth/tidal': { ok: true, user: 'tester' },
  'GET /api/v1/settings/genre-buckets': [
    { id: 1, name: 'Pop', genre_tags: ['pop'], sort_order: 0, is_fallback: false },
    { id: 2, name: 'Other', genre_tags: [], sort_order: 1, is_fallback: true },
  ],
  'GET /api/v1/settings/tag-vocabularies': { energy: [], function: [], crowd: [], mood: [] },
  'GET /api/v1/library/stats': {
    total_local_tracks: 1234,
    with_isrc: 1100,
    formats: { mp3: 1000, flac: 234 },
    matched_event_tracks: 0,
    bucket_distribution: [{ bucket: 'Pop', count: 1234 }],
  },
  [`GET /api/v1/events/${EVENT_ID}/builds`]: [],
  [`GET /api/v1/events/${EVENT_ID}/sync-runs`]: [],
  [`GET /api/v1/events/${EVENT_ID}/tidal-urls`]: { urls: {}, count: 0 },
}

async function mockApi(page: import('@playwright/test').Page) {
  await page.route('**/api/v1/**', async (route: Route) => {
    const req = route.request()
    const url = new URL(req.url())
    const key = `${req.method()} ${url.pathname}`
    const fixture = mockResponses[key]
    if (fixture !== undefined) {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(fixture) })
      return
    }
    // SSE stream — return an empty stream that closes immediately
    if (url.pathname.endsWith('/events/stream') || url.pathname.includes('/jobs/') && url.pathname.endsWith('/events')) {
      await route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' })
      return
    }
    // default: empty 200
    await route.fulfill({ status: 200, contentType: 'application/json', body: 'null' })
  })
}

test.beforeEach(async ({ page }) => {
  await mockApi(page)
})

test('dashboard renders the seeded event', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('Test Wedding')).toBeVisible()
})

test('navigation: dashboard → audit → library → settings', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('link', { name: /audit/i }).click()
  await expect(page).toHaveURL(/\/audit$/)
  await expect(page.getByRole('heading', { name: /audit log/i })).toBeVisible()

  await page.getByRole('link', { name: /library/i }).click()
  await expect(page).toHaveURL(/\/library$/)

  await page.getByRole('link', { name: /settings/i }).click()
  await expect(page).toHaveURL(/\/settings$/)
})

test('audit page lists the mocked entries', async ({ page }) => {
  await page.goto('/audit')
  await expect(page.getByText('tags.apply')).toBeVisible()
  await expect(page.getByText('settings.fs_roots.update')).toBeVisible()
  await expect(page.getByText(/"tracks":\s*12/)).toBeVisible()
})

test('event detail exposes M4 step controls (undo-tags + dry-run checkboxes)', async ({ page }) => {
  await page.goto(`/events/${EVENT_ID}`)
  await expect(page.getByRole('heading', { name: 'Test Wedding' })).toBeVisible()

  // M4 surfaces:
  await expect(page.getByText('Undo last tag write')).toBeVisible()
  await expect(page.getByText(/Restore audio files from per-track snapshots/i)).toBeVisible()

  // Multiple steps now expose a "Dry run" checkbox: apply-tags, undo-tags,
  // build-event, build-library — assert at least 4 of them exist.
  const dryRunBoxes = page.getByLabel('Dry run', { exact: true })
  await expect(dryRunBoxes).toHaveCount(4)
})

test('library page renders stats from mock', async ({ page }) => {
  await page.goto('/library')
  await expect(page.getByText('1234').first()).toBeVisible()
})
