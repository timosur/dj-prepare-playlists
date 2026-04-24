import { useQuery } from '@tanstack/react-query'
import { api } from './api'

export function AuditLog() {
  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['audit'],
    queryFn: () => api.listAudit({ limit: 200 }),
  })

  return (
    <div className="space-y-4 max-w-5xl">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Audit log</h1>
        <button className="text-xs text-crate-500 hover:underline" onClick={() => refetch()} disabled={isFetching}>
          {isFetching ? 'refreshing…' : 'refresh'}
        </button>
      </div>
      <p className="text-xs text-gray-500">
        Most recent {data?.length ?? 0} operations. Use this to trace destructive actions
        (tag writes, builds, syncs) and settings changes.
      </p>

      <div className="card text-xs overflow-x-auto">
        {isLoading && <p className="text-gray-500">Loading…</p>}
        {data && data.length === 0 && <p className="text-gray-500">No entries yet.</p>}
        {data && data.length > 0 && (
          <table className="w-full">
            <thead>
              <tr className="text-left text-gray-500 border-b border-ink-500">
                <th className="py-1 pr-2">When</th>
                <th className="py-1 pr-2">Action</th>
                <th className="py-1 pr-2">Target</th>
                <th className="py-1 pr-2">Payload</th>
              </tr>
            </thead>
            <tbody>
              {data.map((r) => (
                <tr key={r.id} className="border-t border-ink-500 align-top">
                  <td className="py-1 pr-2 text-gray-400 whitespace-nowrap">
                    {new Date(r.ts).toLocaleString()}
                  </td>
                  <td className="py-1 pr-2 font-mono text-crate-500">{r.action}</td>
                  <td className="py-1 pr-2 text-gray-400">
                    {r.target_kind ? <span className="tag bg-ink-500 mr-1">{r.target_kind}</span> : null}
                    <span className="font-mono text-[11px]">{r.target_id || '—'}</span>
                  </td>
                  <td className="py-1 pr-2 text-gray-400">
                    <code className="text-[11px] break-all">
                      {Object.keys(r.payload).length ? JSON.stringify(r.payload) : '—'}
                    </code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
