// Lightweight typed API client. Reads optional bearer token from localStorage.

const TOKEN_KEY = 'cratekeeper.api_token'

function authHeaders(): Record<string, string> {
  const t = localStorage.getItem(TOKEN_KEY)
  return t ? { Authorization: `Bearer ${t}` } : {}
}

export function setApiToken(t: string) {
  localStorage.setItem(TOKEN_KEY, t)
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api/v1${path}`, {
    method,
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`${res.status} ${res.statusText}: ${text}`)
  }
  if (res.status === 204) return undefined as T
  const ct = res.headers.get('content-type') || ''
  if (!ct.includes('application/json')) return undefined as T
  return (await res.json()) as T
}

// ---- Types (mirror cratekeeper-api/schemas.py loosely) -----

export type EventOut = {
  id: string
  name: string
  slug: string
  date: string | null
  source_playlist_url: string | null
  source_playlist_id: string | null
  source_playlist_name: string | null
  build_mode: 'copy' | 'symlink'
  created_at: string
  updated_at: string
  track_count: number
}

export type EventTrackOut = {
  id: string
  event_id: string
  spotify_id: string
  name: string
  artists: string[]
  artist_ids: string[]
  album: string | null
  duration_ms: number
  isrc: string | null
  release_year: number | null
  artist_genres: string[]
  bucket: string | null
  confidence: 'high' | 'medium' | 'low' | null
  match_status: string | null
  match_path: string | null
  bpm: number | null
  audio_energy: number | null
  energy: string | null
  function: string[]
  crowd: string[]
  mood_tags: string[]
  llm_genre_suggestion: string | null
  llm_genre_suggestion_status: string | null
  acquire_later: boolean
}

export type JobOut = {
  id: string
  event_id: string | null
  type: string
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'
  params: Record<string, unknown>
  result: Record<string, unknown> | null
  error: { code?: string; message?: string } | string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export type AnthropicSettingsOut = {
  configured: boolean
  model: string
  prompt_caching: boolean
}

export type SettingsOverview = {
  anthropic_configured: boolean
  spotify_configured: boolean
  tidal_configured: boolean
  fs_roots: string[]
}

export type QualityCheck = {
  name: string
  status: 'pass' | 'warn' | 'fail'
  detail: string | null
  metric: number | null
}

export type QualityReport = {
  overall: 'pass' | 'warn' | 'fail'
  checks: QualityCheck[]
}

// ---- Endpoints -----

export const api = {
  // events
  listEvents: () => request<EventOut[]>('GET', '/events'),
  createEvent: (body: { name: string; date?: string; source_playlist_url?: string; slug?: string; build_mode?: string }) =>
    request<EventOut>('POST', '/events', body),
  getEvent: (id: string) => request<EventOut>('GET', `/events/${id}`),
  updateEvent: (id: string, body: Partial<{ name: string; date: string; slug: string; build_mode: string }>) =>
    request<EventOut>('PATCH', `/events/${id}`, body),
  deleteEvent: (id: string) => request<void>('DELETE', `/events/${id}?confirm=true`),

  // tracks
  listTracks: (eventId: string, q: Record<string, string | undefined> = {}) => {
    const params = new URLSearchParams()
    Object.entries(q).forEach(([k, v]) => v && params.set(k, v))
    const qs = params.toString()
    return request<EventTrackOut[]>('GET', `/events/${eventId}/tracks${qs ? `?${qs}` : ''}`)
  },
  patchTrack: (eventId: string, trackId: string, body: Partial<EventTrackOut>) =>
    request<EventTrackOut>('PATCH', `/events/${eventId}/tracks/${trackId}`, body),
  bulkAction: (eventId: string, body: { track_ids: string[]; action: string; bucket?: string; acquire_later?: boolean }) =>
    request<number>('POST', `/events/${eventId}/tracks/bulk`, body),

  // quality
  qualityChecks: (eventId: string) => request<QualityReport>('GET', `/events/${eventId}/quality-checks`),

  // jobs
  listJobs: (q: Record<string, string | undefined> = {}) => {
    const params = new URLSearchParams()
    Object.entries(q).forEach(([k, v]) => v && params.set(k, v))
    const qs = params.toString()
    return request<JobOut[]>('GET', `/jobs${qs ? `?${qs}` : ''}`)
  },
  enqueueJob: (eventId: string | null, type: string, params: Record<string, unknown> = {}) => {
    const path = eventId ? `/events/${eventId}/jobs` : '/jobs'
    return request<JobOut>('POST', path, { type, params })
  },
  getJob: (id: string) => request<JobOut>('GET', `/jobs/${id}`),
  cancelJob: (id: string) => request<JobOut>('POST', `/jobs/${id}/cancel`),
  resumeJob: (id: string) => request<JobOut>('POST', `/jobs/${id}/resume`),
  jobDependencies: () => request<Record<string, string[]>>('GET', '/jobs/dependencies'),

  // settings
  settingsOverview: () => request<SettingsOverview>('GET', '/settings'),
  getAnthropic: () => request<AnthropicSettingsOut>('GET', '/settings/anthropic'),
  putAnthropic: (body: { api_key?: string; model?: string; prompt_caching: boolean }) =>
    request<AnthropicSettingsOut>('PUT', '/settings/anthropic', body),
  getFsRoots: () => request<{ roots: string[] }>('GET', '/settings/fs-roots'),
  putFsRoots: (roots: string[]) => request<{ roots: string[] }>('PUT', '/settings/fs-roots', { roots }),

  // oauth re-auth (re-uses file-based MCP creds)
  authSpotifyStatus: () => request<{ ok: boolean; user?: string; error?: string }>('GET', '/settings/auth/spotify'),
  authSpotifyRelink: () => request<{ ok: boolean; user?: string; error?: string }>('POST', '/settings/auth/spotify/relink'),
  authTidalStatus: () => request<{ ok: boolean; user?: string; error?: string }>('GET', '/settings/auth/tidal'),
  authTidalRelink: () => request<{ ok: boolean; user?: string; error?: string }>('POST', '/settings/auth/tidal/relink'),

  // genre buckets
  getBuckets: () =>
    request<{ id: number; name: string; genre_tags: string[]; sort_order: number; is_fallback: boolean }[]>(
      'GET',
      '/settings/genre-buckets',
    ),
  putBuckets: (buckets: { name: string; genre_tags: string[]; is_fallback?: boolean }[]) =>
    request<{ id: number; name: string; genre_tags: string[]; sort_order: number; is_fallback: boolean }[]>(
      'PUT',
      '/settings/genre-buckets',
      { buckets },
    ),

  // tag vocabularies
  getTagVocab: () =>
    request<{ energy: string[]; function: string[]; crowd: string[]; mood: string[] }>(
      'GET',
      '/settings/tag-vocabularies',
    ),

  // library
  libraryStats: () =>
    request<{
      total_local_tracks: number
      with_isrc: number
      formats: Record<string, number>
      matched_event_tracks: number
      bucket_distribution: { bucket: string; count: number }[]
    }>('GET', '/library/stats'),

  // event builds + sync runs + tidal urls
  listBuilds: (eventId: string) =>
    request<{ id: string; kind: string; path: string; is_stale: boolean; last_built_at: string | null; summary: Record<string, unknown> }[]>(
      'GET',
      `/events/${eventId}/builds`,
    ),
  listSyncRuns: (eventId: string) =>
    request<{ id: string; platform: string; job_id: string | null; summary: Record<string, unknown>; created_at: string }[]>(
      'GET',
      `/events/${eventId}/sync-runs`,
    ),
  tidalUrls: (eventId: string) =>
    request<{ urls: Record<string, string | null>; count: number }>('GET', `/events/${eventId}/tidal-urls`),

  // audit log
  listAudit: (params?: { target_kind?: string; target_id?: string; limit?: number }) => {
    const q = new URLSearchParams()
    if (params?.target_kind) q.set('target_kind', params.target_kind)
    if (params?.target_id) q.set('target_id', params.target_id)
    if (params?.limit) q.set('limit', String(params.limit))
    const suffix = q.toString() ? `?${q.toString()}` : ''
    return request<
      { id: number; ts: string; actor: string; action: string; target_kind: string | null; target_id: string | null; payload: Record<string, unknown> }[]
    >('GET', `/audit${suffix}`)
  },
}
