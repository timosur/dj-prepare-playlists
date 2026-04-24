import { useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { CheckCircle2, XCircle } from 'lucide-react'
import { api, setApiToken } from './api'
import { GenreBucketEditor } from './GenreBucketEditor'

type AnthForm = { api_key: string; model: string; prompt_caching: boolean }

export function Settings() {
  const qc = useQueryClient()
  const { data: overview } = useQuery({ queryKey: ['settings', 'overview'], queryFn: api.settingsOverview })
  const { data: anth } = useQuery({ queryKey: ['settings', 'anthropic'], queryFn: api.getAnthropic })
  const { data: roots } = useQuery({ queryKey: ['settings', 'roots'], queryFn: api.getFsRoots })

  const { register, handleSubmit, reset } = useForm<AnthForm>({
    defaultValues: { api_key: '', model: 'claude-sonnet-4-6', prompt_caching: true },
  })
  useEffect(() => {
    if (anth) reset({ api_key: '', model: anth.model, prompt_caching: anth.prompt_caching })
  }, [anth, reset])

  const saveAnth = useMutation({
    mutationFn: (v: AnthForm) => api.putAnthropic({
      api_key: v.api_key || undefined,
      model: v.model,
      prompt_caching: v.prompt_caching,
    }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['settings'] }),
  })

  return (
    <div className="space-y-6 max-w-3xl">
      <h1 className="text-2xl font-semibold">Settings</h1>

      <section>
        <h2 className="text-sm uppercase tracking-wide text-gray-400 mb-2">Integrations</h2>
        <div className="card grid grid-cols-3 gap-3 text-sm">
          <Indicator label="Spotify" ok={!!overview?.spotify_configured} hint="Token from spotify-mcp/spotify-config.json (auto-refreshing)" />
          <Indicator label="Tidal" ok={!!overview?.tidal_configured} hint="Session from tidal-mcp/tidal-session.json" />
          <Indicator label="Anthropic" ok={!!overview?.anthropic_configured} hint="API key required for tag classification" />
        </div>
        <div className="card mt-2 grid grid-cols-2 gap-3 text-xs">
          <RelinkRow label="Spotify" statusFn={api.authSpotifyStatus} relinkFn={api.authSpotifyRelink} />
          <RelinkRow label="Tidal" statusFn={api.authTidalStatus} relinkFn={api.authTidalRelink} />
        </div>
      </section>

      <section>
        <h2 className="text-sm uppercase tracking-wide text-gray-400 mb-2">Anthropic (LLM tag classifier)</h2>
        <form onSubmit={handleSubmit((v) => saveAnth.mutate(v))} className="card space-y-3">
          <div>
            <label className="label">API key {anth?.configured && <span className="text-green-500">(currently set — leave blank to keep)</span>}</label>
            <input type="password" className="input" autoComplete="new-password" {...register('api_key')} placeholder="sk-ant-…" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Model</label>
              <input className="input" {...register('model')} />
            </div>
            <div className="flex items-end gap-2">
              <input id="pc" type="checkbox" {...register('prompt_caching')} className="accent-crate-500" />
              <label htmlFor="pc" className="text-sm">Prompt caching (recommended)</label>
            </div>
          </div>
          <div className="flex justify-end">
            <button className="btn-primary" disabled={saveAnth.isPending}>{saveAnth.isPending ? 'Saving…' : 'Save'}</button>
          </div>
        </form>
      </section>

      <section>
        <h2 className="text-sm uppercase tracking-wide text-gray-400 mb-2">Filesystem roots</h2>
        <div className="card text-sm">
          <p className="text-gray-400 mb-2">Allowed roots for scan / build operations.</p>
          <ul className="space-y-1">
            {roots?.roots.map((r) => <li key={r} className="font-mono text-xs">{r}</li>)}
          </ul>
        </div>
      </section>

      <section>
        <h2 className="text-sm uppercase tracking-wide text-gray-400 mb-2">API auth</h2>
        <div className="card text-sm space-y-2">
          <p className="text-gray-400">Set a bearer token (matches CRATEKEEPER_API_TOKEN). Leave blank if backend has no token configured.</p>
          <input className="input" placeholder="Bearer token"
                 onChange={(e) => setApiToken(e.target.value)} />
        </div>
      </section>

      <GenreBucketEditor />
    </div>
  )
}

function Indicator({ label, ok, hint }: { label: string; ok: boolean; hint: string }) {
  return (
    <div>
      <div className="flex items-center gap-1.5 font-medium">
        {ok ? <CheckCircle2 size={16} className="text-green-500" /> : <XCircle size={16} className="text-red-500" />}
        {label}
      </div>
      <p className="text-xs text-gray-500 mt-1">{hint}</p>
    </div>
  )
}

function RelinkRow({
  label,
  statusFn,
  relinkFn,
}: {
  label: string
  statusFn: () => Promise<{ ok: boolean; user?: string; error?: string }>
  relinkFn: () => Promise<{ ok: boolean; user?: string; error?: string }>
}) {
  const qc = useQueryClient()
  const { data, refetch, isFetching } = useQuery({
    queryKey: ['auth', label],
    queryFn: statusFn,
    retry: false,
  })
  const relink = useMutation({
    mutationFn: relinkFn,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['auth', label] })
      qc.invalidateQueries({ queryKey: ['settings', 'overview'] })
    },
  })
  return (
    <div className="flex items-center gap-2">
      <span className="font-medium w-16">{label}</span>
      {data?.ok ? (
        <span className="text-green-500 truncate flex-1">linked as {data.user}</span>
      ) : (
        <span className="text-red-500 truncate flex-1">{data?.error || 'not linked'}</span>
      )}
      <button
        className="text-crate-500 hover:underline disabled:opacity-50"
        onClick={() => relink.mutate()}
        disabled={isFetching || relink.isPending}
      >
        re-link
      </button>
      <button className="text-gray-500 hover:underline" onClick={() => refetch()} disabled={isFetching}>
        check
      </button>
    </div>
  )
}
