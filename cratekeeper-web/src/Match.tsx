import { useQuery } from '@tanstack/react-query'
import { api } from './api'

export function MatchPanel({ eventId }: { eventId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['tidal-urls', eventId],
    queryFn: () => api.tidalUrls(eventId),
    retry: false,
  })

  const entries = data ? Object.entries(data.urls) : []
  if (!isLoading && entries.length === 0) return null

  return (
    <section>
      <h2 className="text-sm uppercase tracking-wide text-gray-400 mb-2">Unmatched ({entries.length})</h2>
      <div className="card text-xs">
        {isLoading && <p className="text-gray-500">Resolving Tidal URLs…</p>}
        {!isLoading && (
          <>
            <p className="text-gray-400 mb-2">{data?.count} of {entries.length} ISRCs found on Tidal — open to acquire.</p>
            <ul className="space-y-1 max-h-64 overflow-auto">
              {entries.map(([isrc, url]) => (
                <li key={isrc} className="flex items-center gap-2">
                  <span className="font-mono text-gray-500 w-32">{isrc}</span>
                  {url ? (
                    <a className="text-crate-500 hover:underline truncate" href={url} target="_blank" rel="noreferrer">{url}</a>
                  ) : (
                    <span className="text-gray-600">— not on Tidal —</span>
                  )}
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </section>
  )
}
