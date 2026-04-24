import { useQuery } from '@tanstack/react-query'
import { api } from './api'

export function MasterLibrary() {
  const { data, isLoading, error } = useQuery({ queryKey: ['library', 'stats'], queryFn: api.libraryStats })

  return (
    <div className="space-y-6 max-w-4xl">
      <h1 className="text-2xl font-semibold">Master library</h1>

      {isLoading && <p className="text-gray-400">Loading…</p>}
      {error && <p className="text-red-500">Failed to load: {(error as Error).message}</p>}

      {data && (
        <>
          <section>
            <div className="card grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
              <Stat label="Local tracks" value={data.total_local_tracks} />
              <Stat label="With ISRC" value={`${data.with_isrc} (${pct(data.with_isrc, data.total_local_tracks)}%)`} />
              <Stat label="Matched event tracks" value={data.matched_event_tracks} />
              <Stat label="Formats" value={Object.keys(data.formats).length} />
            </div>
          </section>

          <section>
            <h2 className="text-sm uppercase tracking-wide text-gray-400 mb-2">Formats</h2>
            <div className="card text-xs space-y-1">
              {Object.entries(data.formats).map(([k, v]) => (
                <div key={k} className="flex items-center gap-2">
                  <span className="w-20 font-mono text-gray-400">{k}</span>
                  <span className="text-gray-300">{v}</span>
                </div>
              ))}
            </div>
          </section>

          <section>
            <h2 className="text-sm uppercase tracking-wide text-gray-400 mb-2">Bucket distribution (across events)</h2>
            <div className="card text-xs space-y-1">
              {data.bucket_distribution.length === 0 && <p className="text-gray-500">No tracks classified yet.</p>}
              {data.bucket_distribution.map((b) => {
                const max = data.bucket_distribution[0]?.count || 1
                return (
                  <div key={b.bucket} className="flex items-center gap-2">
                    <span className="w-40 truncate">{b.bucket}</span>
                    <div className="flex-1 bg-ink-500 h-3 rounded">
                      <div className="bg-crate-500 h-3 rounded" style={{ width: `${(b.count / max) * 100}%` }} />
                    </div>
                    <span className="w-10 text-right text-gray-400">{b.count}</span>
                  </div>
                )
              })}
            </div>
          </section>
        </>
      )}
    </div>
  )
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div>
      <div className="text-xs text-gray-500">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  )
}

function pct(a: number, b: number): number {
  if (!b) return 0
  return Math.round((a / b) * 100)
}
