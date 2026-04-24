import { useQuery } from '@tanstack/react-query'
import { AlertTriangle } from 'lucide-react'
import { api } from './api'

export function BuildPanel({ eventId }: { eventId: string }) {
  const { data } = useQuery({ queryKey: ['builds', eventId], queryFn: () => api.listBuilds(eventId), retry: false })
  if (!data || data.length === 0) return null

  return (
    <section>
      <h2 className="text-sm uppercase tracking-wide text-gray-400 mb-2">Builds</h2>
      <div className="card space-y-2 text-xs">
        {data.map((b) => (
          <div key={b.id} className="flex items-center gap-3">
            <span className="tag bg-ink-500">{b.kind}</span>
            <span className="font-mono text-gray-300 truncate flex-1">{b.path}</span>
            {b.is_stale && (
              <span className="flex items-center gap-1 text-yellow-500">
                <AlertTriangle size={12} /> stale — re-run
              </span>
            )}
            <span className="text-gray-500">
              {b.last_built_at ? new Date(b.last_built_at).toLocaleString() : '—'}
            </span>
            <span className="text-gray-400">
              {(b.summary as { created?: number; copied?: number; missing?: number }).created ??
                (b.summary as { copied?: number }).copied ?? 0}
              {' files, '}
              {(b.summary as { missing?: number }).missing ?? 0} missing
            </span>
          </div>
        ))}
      </div>
    </section>
  )
}
