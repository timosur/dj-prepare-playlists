import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useForm } from 'react-hook-form'
import { Calendar, Disc3, Plus } from 'lucide-react'
import { api } from './api'

type CreateForm = { name: string; date?: string; source_playlist_url?: string }

export function Dashboard() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: ['events'], queryFn: api.listEvents })
  const [showCreate, setShowCreate] = useState(false)
  const { register, handleSubmit, reset } = useForm<CreateForm>()
  const createMut = useMutation({
    mutationFn: (body: CreateForm) => api.createEvent(body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['events'] }); reset(); setShowCreate(false) },
  })

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-semibold">Events</h1>
        <button className="btn-primary" onClick={() => setShowCreate((v) => !v)}>
          <Plus size={16} /> New event
        </button>
      </div>

      {showCreate && (
        <form onSubmit={handleSubmit((v) => createMut.mutate(v))} className="card mb-4 space-y-3">
          <div>
            <label className="label">Event name</label>
            <input className="input" placeholder="Anna & Tom Wedding" {...register('name', { required: true })} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Date</label>
              <input className="input" type="date" {...register('date')} />
            </div>
            <div>
              <label className="label">Spotify wishlist URL or ID</label>
              <input className="input" placeholder="https://open.spotify.com/playlist/..." {...register('source_playlist_url')} />
            </div>
          </div>
          {createMut.error && <p className="text-red-400 text-sm">{(createMut.error as Error).message}</p>}
          <div className="flex gap-2 justify-end">
            <button type="button" className="btn-ghost" onClick={() => setShowCreate(false)}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={createMut.isPending}>
              {createMut.isPending ? 'Creating…' : 'Create'}
            </button>
          </div>
        </form>
      )}

      {isLoading && <p className="text-gray-400">Loading…</p>}
      {data && data.length === 0 && (
        <div className="card text-center py-12">
          <Disc3 className="mx-auto text-gray-500 mb-3" size={32} />
          <p className="text-gray-400">No events yet. Create one to start a wishlist intake.</p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {data?.map((ev) => (
          <Link to="/events/$eventId" params={{ eventId: ev.id }} key={ev.id} className="card hover:border-crate-500 transition">
            <div className="flex items-baseline justify-between">
              <h3 className="font-semibold">{ev.name}</h3>
              <span className="text-xs text-gray-500">{ev.track_count} tracks</span>
            </div>
            <div className="text-xs text-gray-400 mt-1">/{ev.slug}</div>
            {ev.date && <div className="text-xs text-gray-400 mt-1 flex items-center gap-1"><Calendar size={12} />{ev.date}</div>}
            {ev.source_playlist_name && <div className="text-xs mt-2 text-gray-300 truncate">{ev.source_playlist_name}</div>}
          </Link>
        ))}
      </div>
    </div>
  )
}
