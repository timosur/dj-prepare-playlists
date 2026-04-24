import { useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useQuery } from '@tanstack/react-query'
import { api, type EventTrackOut } from './api'

export function ReviewPanel({ eventId, tracks }: { eventId: string; tracks: EventTrackOut[] }) {
  const qc = useQueryClient()
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [bucket, setBucket] = useState('')
  const { data: buckets } = useQuery({ queryKey: ['buckets'], queryFn: api.getBuckets })

  const lowConf = useMemo(
    () => tracks.filter((t) => t.confidence === 'low' || t.confidence === 'medium'),
    [tracks],
  )
  const pendingTags = useMemo(
    () => tracks.filter((t) => t.llm_genre_suggestion && t.llm_genre_suggestion_status === 'pending'),
    [tracks],
  )

  const bulk = useMutation({
    mutationFn: (action: { action: string; bucket?: string }) =>
      api.bulkAction(eventId, { track_ids: Array.from(selected), ...action }),
    onSuccess: () => {
      setSelected(new Set())
      qc.invalidateQueries({ queryKey: ['tracks', eventId] })
    },
  })

  const toggle = (id: string) =>
    setSelected((s) => {
      const next = new Set(s)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })

  if (lowConf.length === 0 && pendingTags.length === 0) return null

  return (
    <section>
      <h2 className="text-sm uppercase tracking-wide text-gray-400 mb-2">Review</h2>

      {lowConf.length > 0 && (
        <div className="card space-y-2">
          <div className="flex items-center gap-3 text-sm">
            <span className="text-gray-400">{selected.size} selected</span>
            <select className="input flex-1 max-w-xs text-sm" value={bucket} onChange={(e) => setBucket(e.target.value)}>
              <option value="">— pick bucket —</option>
              {buckets?.map((b) => <option key={b.id} value={b.name}>{b.name}</option>)}
            </select>
            <button
              className="btn-primary text-xs"
              disabled={selected.size === 0 || !bucket || bulk.isPending}
              onClick={() => bulk.mutate({ action: 'rebucket', bucket })}
            >
              Re-bucket
            </button>
            <button
              className="text-xs text-crate-500 hover:underline"
              disabled={selected.size === 0 || bulk.isPending}
              onClick={() => bulk.mutate({ action: 'set_acquire_later' })}
            >
              Mark acquire-later
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <tbody>
                {lowConf.slice(0, 100).map((t) => (
                  <tr key={t.id} className="border-t border-ink-500">
                    <td className="py-1 pr-2 w-6">
                      <input type="checkbox" className="accent-crate-500" checked={selected.has(t.id)} onChange={() => toggle(t.id)} />
                    </td>
                    <td className="py-1 pr-2">{t.name}</td>
                    <td className="py-1 pr-2 text-gray-400">{t.artists.join(', ')}</td>
                    <td className="py-1 pr-2"><span className="tag">{t.bucket || '—'}</span></td>
                    <td className="py-1 pr-2 text-yellow-500">{t.confidence}</td>
                    <td className="py-1 pr-2 text-gray-500 text-[11px]">{(t.artist_genres || []).slice(0, 3).join(', ')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {pendingTags.length > 0 && (
        <div className="card mt-3 space-y-2">
          <h3 className="text-sm font-semibold text-gray-300">Pending LLM bucket suggestions ({pendingTags.length})</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <tbody>
                {pendingTags.slice(0, 100).map((t) => (
                  <tr key={t.id} className="border-t border-ink-500">
                    <td className="py-1 pr-2">{t.name}</td>
                    <td className="py-1 pr-2 text-gray-400">{t.artists.join(', ')}</td>
                    <td className="py-1 pr-2 text-gray-500">{t.bucket} → <span className="text-crate-500">{t.llm_genre_suggestion}</span></td>
                    <td className="py-1 pr-2 text-right">
                      <button
                        className="text-xs text-green-500 hover:underline mr-3"
                        onClick={() => api.bulkAction(eventId, { track_ids: [t.id], action: 'accept_genre_suggestion' }).then(() => qc.invalidateQueries({ queryKey: ['tracks', eventId] }))}
                      >accept</button>
                      <button
                        className="text-xs text-gray-500 hover:underline"
                        onClick={() => api.bulkAction(eventId, { track_ids: [t.id], action: 'ignore_genre_suggestion' }).then(() => qc.invalidateQueries({ queryKey: ['tracks', eventId] }))}
                      >ignore</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  )
}
