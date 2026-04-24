import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowDown, ArrowUp, Plus, Trash2 } from 'lucide-react'
import { api } from './api'

type Row = { name: string; genre_tags: string[]; is_fallback: boolean }

export function GenreBucketEditor() {
  const qc = useQueryClient()
  const { data } = useQuery({ queryKey: ['buckets'], queryFn: api.getBuckets })
  const [rows, setRows] = useState<Row[]>([])
  const [dirty, setDirty] = useState(false)

  useEffect(() => {
    if (data && !dirty) {
      setRows(data.map((b) => ({ name: b.name, genre_tags: b.genre_tags, is_fallback: b.is_fallback })))
    }
  }, [data, dirty])

  const save = useMutation({
    mutationFn: (next: Row[]) => api.putBuckets(next),
    onSuccess: () => {
      setDirty(false)
      qc.invalidateQueries({ queryKey: ['buckets'] })
    },
  })

  const move = (i: number, dir: -1 | 1) => {
    const j = i + dir
    if (j < 0 || j >= rows.length) return
    const next = rows.slice()
    ;[next[i], next[j]] = [next[j], next[i]]
    setRows(next)
    setDirty(true)
  }

  const update = (i: number, patch: Partial<Row>) => {
    const next = rows.slice()
    next[i] = { ...next[i], ...patch }
    setRows(next)
    setDirty(true)
  }

  const remove = (i: number) => {
    setRows(rows.filter((_, idx) => idx !== i))
    setDirty(true)
  }

  const add = () => {
    setRows([...rows, { name: 'New bucket', genre_tags: [], is_fallback: false }])
    setDirty(true)
  }

  return (
    <section>
      <h2 className="text-sm uppercase tracking-wide text-gray-400 mb-2">Genre buckets</h2>
      <div className="card space-y-2 text-sm">
        <p className="text-xs text-gray-500">Order is meaningful — first match wins. The fallback bucket catches everything else.</p>
        {rows.map((r, i) => (
          <div key={i} className="flex items-center gap-2 border-t border-ink-500 pt-2">
            <div className="flex flex-col">
              <button className="text-gray-500 hover:text-crate-500" onClick={() => move(i, -1)} disabled={i === 0}><ArrowUp size={12} /></button>
              <button className="text-gray-500 hover:text-crate-500" onClick={() => move(i, 1)} disabled={i === rows.length - 1}><ArrowDown size={12} /></button>
            </div>
            <input
              className="input flex-1 text-sm"
              value={r.name}
              onChange={(e) => update(i, { name: e.target.value })}
            />
            <input
              className="input flex-[2] text-xs font-mono"
              placeholder="comma-separated genre tags"
              value={r.genre_tags.join(', ')}
              onChange={(e) => update(i, { genre_tags: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })}
            />
            <label className="text-xs text-gray-400 flex items-center gap-1">
              <input type="checkbox" className="accent-crate-500" checked={r.is_fallback} onChange={(e) => update(i, { is_fallback: e.target.checked })} />
              fallback
            </label>
            <button className="text-gray-500 hover:text-red-500" onClick={() => remove(i)}><Trash2 size={14} /></button>
          </div>
        ))}
        <div className="flex justify-between pt-2">
          <button className="text-xs text-crate-500 flex items-center gap-1 hover:underline" onClick={add}>
            <Plus size={12} /> Add bucket
          </button>
          <button
            className="btn-primary text-xs"
            disabled={!dirty || save.isPending}
            onClick={() => save.mutate(rows)}
          >
            {save.isPending ? 'Saving…' : 'Save buckets'}
          </button>
        </div>
      </div>
    </section>
  )
}
