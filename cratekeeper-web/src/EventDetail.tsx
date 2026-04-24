import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams } from '@tanstack/react-router'
import { Play } from 'lucide-react'
import { api, type JobOut } from './api'
import { JobProgress } from './JobProgress'
import { ReviewPanel } from './Review'
import { MatchPanel } from './Match'
import { AnalyzePanel } from './Analyze'
import { BuildPanel } from './Build'
import { SyncPanel } from './Sync'

type Step = {
  type: string
  label: string
  description: string
  needsPlaylist?: boolean
  paramFields?: { name: string; label: string; placeholder?: string; type?: 'text' | 'checkbox' }[]
}

const STEPS: Step[] = [
  { type: 'fetch', label: 'Intake', description: 'Pull tracks from Spotify wishlist (with ISRCs + artist genres).', needsPlaylist: true },
  { type: 'enrich', label: 'Enrich (MusicBrainz)', description: 'Fill missing artist genres and original release year via MusicBrainz ISRC lookup (~1 req/sec).' },
  { type: 'classify', label: 'Classify', description: 'Bucket tracks into genres using artist tags.' },
  {
    type: 'scan-incremental',
    label: 'Scan (incremental)',
    description: 'Index a local audio root into the library DB (skips files already seen). Library-wide; not event-scoped.',
    paramFields: [{ name: 'root', label: 'Root', placeholder: '/Volumes/Music', type: 'text' }],
  },
  {
    type: 'match',
    label: 'Match',
    description: 'Map event tracks to local files via ISRC / exact / fuzzy.',
    paramFields: [{ name: 'fuzzy_threshold', label: 'Fuzzy threshold', placeholder: '85', type: 'text' }],
  },
  {
    type: 'analyze-mood',
    label: 'Analyze',
    description: 'Extract BPM / key / energy / mood with Essentia.',
    paramFields: [{ name: 'force', label: 'Re-analyze already done', type: 'checkbox' }],
  },
  { type: 'classify-tags', label: 'Tag (LLM)', description: 'Anthropic Sonnet → energy / function / crowd / mood (uses audio analysis).' },
  {
    type: 'apply-tags',
    label: 'Write tags',
    description: 'Embed bucket / BPM / key / LLM tags into local audio files (snapshots originals). Must run before build steps.',
    paramFields: [{ name: 'dry_run', label: 'Dry run', type: 'checkbox' }],
  },
  {
    type: 'undo-tags',
    label: 'Undo last tag write',
    description: 'Restore audio files from per-track snapshots created by the previous tag-write.',
    paramFields: [{ name: 'dry_run', label: 'Dry run', type: 'checkbox' }],
  },
  {
    type: 'build-library',
    label: 'Build library',
    description: 'Refresh the master Genre/ library from all matched event tracks. Library-wide; not event-scoped.',
    paramFields: [
      { name: 'output_dir', label: 'Output dir', placeholder: '~/Music/Library', type: 'text' },
      { name: 'dry_run', label: 'Dry run', type: 'checkbox' },
    ],
  },
  {
    type: 'build-event',
    label: 'Build event folder',
    description: 'Create a Genre/Artist - Title.ext folder for this event.',
    paramFields: [
      { name: 'output_dir', label: 'Output dir', placeholder: '~/Music/EventBuilds', type: 'text' },
      { name: 'dry_run', label: 'Dry run', type: 'checkbox' },
    ],
  },
  {
    type: 'sync-spotify',
    label: 'Sync → Spotify',
    description: 'Create a Spotify playlist with all matched tracks.',
    paramFields: [{ name: 'name', label: 'Playlist name (blank = auto)', type: 'text' }],
  },
  {
    type: 'sync-tidal',
    label: 'Sync → Tidal',
    description: 'Create a Tidal playlist for tracks with ISRCs.',
    paramFields: [{ name: 'name', label: 'Playlist name (blank = auto)', type: 'text' }],
  },
]

export function EventDetail() {
  const { eventId } = useParams({ from: '/events/$eventId' })
  const qc = useQueryClient()
  const { data: ev } = useQuery({ queryKey: ['event', eventId], queryFn: () => api.getEvent(eventId) })
  const { data: tracks } = useQuery({ queryKey: ['tracks', eventId], queryFn: () => api.listTracks(eventId) })
  const { data: jobs } = useQuery({
    queryKey: ['jobs', eventId],
    queryFn: () => api.listJobs({ event_id: eventId }),
    refetchInterval: 3000,
  })
  const { data: deps } = useQuery({
    queryKey: ['job-dependencies'],
    queryFn: () => api.jobDependencies(),
    staleTime: Infinity,
  })
  const { data: quality } = useQuery({ queryKey: ['quality', eventId], queryFn: () => api.qualityChecks(eventId), retry: false })

  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const [stepParams, setStepParams] = useState<Record<string, Record<string, string | boolean>>>({})

  const enqueue = useMutation({
    mutationFn: ({ type, params }: { type: string; params?: Record<string, unknown> }) =>
      api.enqueueJob(eventId, type, params || {}),
    onSuccess: (job) => {
      setActiveJobId(job.id)
      qc.invalidateQueries({ queryKey: ['jobs', eventId] })
    },
  })

  if (!ev) return <p className="text-gray-400">Loading…</p>

  const setStepParam = (type: string, name: string, value: string | boolean) =>
    setStepParams((p) => ({ ...p, [type]: { ...(p[type] || {}), [name]: value } }))

  const collectParams = (s: Step): Record<string, unknown> => {
    const raw = stepParams[s.type] || {}
    const out: Record<string, unknown> = {}
    s.paramFields?.forEach((f) => {
      const v = raw[f.name]
      if (v === undefined || v === '') return
      if (f.name === 'fuzzy_threshold') out[f.name] = Number(v)
      else out[f.name] = v
    })
    return out
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">{ev.name}</h1>
        <div className="text-sm text-gray-400">/{ev.slug} · {ev.track_count} tracks {ev.date && `· ${ev.date}`}</div>
        {ev.source_playlist_url && (
          <a className="text-xs text-crate-500 hover:underline" href={ev.source_playlist_url} target="_blank" rel="noreferrer">
            {ev.source_playlist_name || ev.source_playlist_url}
          </a>
        )}
      </header>

      <section>
        <h2 className="text-sm uppercase tracking-wide text-gray-400 mb-2">Pipeline</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {STEPS.map((s) => {
            const last = jobs?.find((j) => j.type === s.type)
            const succeededTypes = new Set(
              (jobs ?? []).filter((j) => j.status === 'succeeded').map((j) => j.type),
            )
            const prereqs = deps?.[s.type] ?? []
            const missingPrereqs = prereqs.filter((t) => !succeededTypes.has(t))
            const blockedByPrereqs = missingPrereqs.length > 0
            const disabled =
              enqueue.isPending ||
              (s.needsPlaylist && !ev.source_playlist_url) ||
              blockedByPrereqs
            const prereqLabels = (types: string[]) =>
              types
                .map((t) => STEPS.find((step) => step.type === t)?.label ?? t)
                .join(', ')
            return (
              <div key={s.type} className="card flex flex-col gap-2">
                <div className="flex justify-between items-baseline">
                  <h3 className="font-semibold">{s.label}</h3>
                  {last && <StatusBadge status={last.status} />}
                </div>
                <p className="text-xs text-gray-400">{s.description}</p>
                {prereqs.length > 0 && (
                  <p className={'text-xs ' + (blockedByPrereqs ? 'text-amber-400' : 'text-gray-500')}>
                    {blockedByPrereqs
                      ? `Requires: ${prereqLabels(missingPrereqs)}`
                      : `After: ${prereqLabels(prereqs)}`}
                  </p>
                )}
                {s.paramFields?.map((f) => (
                  <div key={f.name} className="flex items-center gap-2 text-xs">
                    {f.type === 'checkbox' ? (
                      <>
                        <input
                          id={`${s.type}-${f.name}`}
                          type="checkbox"
                          className="accent-crate-500"
                          checked={!!stepParams[s.type]?.[f.name]}
                          onChange={(e) => setStepParam(s.type, f.name, e.target.checked)}
                        />
                        <label htmlFor={`${s.type}-${f.name}`}>{f.label}</label>
                      </>
                    ) : (
                      <>
                        <label className="text-gray-500 w-32">{f.label}</label>
                        <input
                          className="input flex-1 text-xs py-1"
                          placeholder={f.placeholder}
                          value={(stepParams[s.type]?.[f.name] as string) || ''}
                          onChange={(e) => setStepParam(s.type, f.name, e.target.value)}
                        />
                      </>
                    )}
                  </div>
                ))}
                <button
                  className="btn-primary self-start"
                  disabled={disabled}
                  onClick={() => enqueue.mutate({ type: s.type, params: collectParams(s) })}
                >
                  <Play size={14} /> Run
                </button>
                {last && (
                  <button className="text-xs text-crate-500 hover:underline self-start" onClick={() => setActiveJobId(last.id)}>
                    view last run
                  </button>
                )}
              </div>
            )
          })}
        </div>
      </section>

      {activeJobId && (
        <section>
          <h2 className="text-sm uppercase tracking-wide text-gray-400 mb-2">Active job</h2>
          <JobProgress
            jobId={activeJobId}
            onDone={() => {
              qc.invalidateQueries({ queryKey: ['tracks', eventId] })
              qc.invalidateQueries({ queryKey: ['quality', eventId] })
              qc.invalidateQueries({ queryKey: ['event', eventId] })
              qc.invalidateQueries({ queryKey: ['builds', eventId] })
              qc.invalidateQueries({ queryKey: ['sync-runs', eventId] })
              qc.invalidateQueries({ queryKey: ['tidal-urls', eventId] })
            }}
          />
        </section>
      )}

      {quality && (
        <section>
          <h2 className="text-sm uppercase tracking-wide text-gray-400 mb-2">Quality</h2>
          <div className="card space-y-2 text-sm">
            <div className="flex items-center gap-2">
              <span className="text-xs uppercase text-gray-500">Overall</span>
              <span
                className={
                  'tag ' +
                  (quality.overall === 'pass'
                    ? 'bg-emerald-700'
                    : quality.overall === 'warn'
                    ? 'bg-amber-700'
                    : 'bg-rose-700')
                }
              >
                {quality.overall}
              </span>
            </div>
            <ul className="divide-y divide-ink-500">
              {(quality.checks ?? []).map((c) => (
                <li key={c.name} className="py-1 flex items-start gap-2">
                  <span
                    className={
                      'tag shrink-0 ' +
                      (c.status === 'pass'
                        ? 'bg-emerald-700'
                        : c.status === 'warn'
                        ? 'bg-amber-700'
                        : 'bg-rose-700')
                    }
                  >
                    {c.status}
                  </span>
                  <div className="flex-1">
                    <div className="font-medium">{c.name}</div>
                    {c.detail && <div className="text-xs text-gray-400">{c.detail}</div>}
                  </div>
                  {c.metric != null && (
                    <span className="text-xs text-gray-400 font-mono">{c.metric}</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </section>
      )}

      <ReviewPanel eventId={eventId} tracks={tracks || []} />
      <MatchPanel eventId={eventId} />
      <AnalyzePanel tracks={tracks || []} />
      <BuildPanel eventId={eventId} />
      <SyncPanel eventId={eventId} />

      <section>
        <h2 className="text-sm uppercase tracking-wide text-gray-400 mb-2">Tracks ({tracks?.length || 0})</h2>
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase text-gray-500">
              <tr>
                <th className="py-1 pr-2">Title</th>
                <th className="py-1 pr-2">Artists</th>
                <th className="py-1 pr-2">Bucket</th>
                <th className="py-1 pr-2">Conf</th>
                <th className="py-1 pr-2">Match</th>
                <th className="py-1 pr-2">BPM</th>
                <th className="py-1 pr-2">Energy</th>
                <th className="py-1">Year</th>
              </tr>
            </thead>
            <tbody>
              {tracks?.slice(0, 200).map((t) => (
                <tr key={t.id} className="border-t border-ink-500">
                  <td className="py-1 pr-2">{t.name}</td>
                  <td className="py-1 pr-2 text-gray-300">{t.artists.join(', ')}</td>
                  <td className="py-1 pr-2"><span className="tag">{t.bucket || '—'}</span></td>
                  <td className="py-1 pr-2">{t.confidence || '—'}</td>
                  <td className="py-1 pr-2 text-xs">{t.match_status || '—'}</td>
                  <td className="py-1 pr-2">{t.bpm ? Math.round(t.bpm) : '—'}</td>
                  <td className="py-1 pr-2">{t.energy || '—'}</td>
                  <td className="py-1 text-gray-400">{t.release_year || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2 className="text-sm uppercase tracking-wide text-gray-400 mb-2">Job history</h2>
        <div className="card space-y-1 text-sm">
          {jobs?.length === 0 && <p className="text-gray-500">No jobs yet.</p>}
          {jobs?.map((j) => (
            <div key={j.id} className="flex items-center gap-3 py-1">
              <StatusBadge status={j.status} />
              <span className="text-gray-300 w-44">{j.type}</span>
              <span className="text-xs text-gray-500 flex-1">{new Date(j.created_at).toLocaleString()}</span>
              <button className="text-xs text-crate-500 hover:underline" onClick={() => setActiveJobId(j.id)}>
                view
              </button>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

function StatusBadge({ status }: { status: JobOut['status'] }) {
  const cls = {
    queued: 'bg-yellow-700',
    running: 'bg-blue-700',
    succeeded: 'bg-green-700',
    failed: 'bg-red-700',
    cancelled: 'bg-gray-700',
  }[status]
  return <span className={`tag ${cls}`}>{status}</span>
}
