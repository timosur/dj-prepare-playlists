import { useQuery } from '@tanstack/react-query'
import { ExternalLink } from 'lucide-react'
import { api } from './api'

export function SyncPanel({ eventId }: { eventId: string }) {
  const { data } = useQuery({ queryKey: ['sync-runs', eventId], queryFn: () => api.listSyncRuns(eventId), retry: false })
  if (!data || data.length === 0) return null

  return (
    <section>
      <h2 className="text-sm uppercase tracking-wide text-gray-400 mb-2">Playlist syncs</h2>
      <div className="card space-y-2 text-xs">
        {data.map((r) => {
          const s = r.summary as { name?: string; url?: string; added?: number; failed?: number }
          return (
            <div key={r.id} className="flex items-center gap-3">
              <span className={`tag ${r.platform === 'spotify' ? 'bg-green-700' : 'bg-blue-700'}`}>{r.platform}</span>
              <span className="text-gray-300 flex-1 truncate">{s.name || '—'}</span>
              <span className="text-gray-400">{s.added ?? 0} added{s.failed ? ` · ${s.failed} failed` : ''}</span>
              {s.url && (
                <a className="text-crate-500 hover:underline flex items-center gap-1" href={s.url} target="_blank" rel="noreferrer">
                  open <ExternalLink size={11} />
                </a>
              )}
              <span className="text-gray-500">{new Date(r.created_at).toLocaleString()}</span>
            </div>
          )
        })}
      </div>
    </section>
  )
}
