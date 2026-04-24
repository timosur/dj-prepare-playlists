import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, type JobOut } from './api'
import { useSSE } from './sse'
import clsx from 'clsx'

type ProgressData = { current?: number; total?: number; pct?: number; item?: { display?: string; track_id?: string } }
type LogData = { message?: string }
type CostData = { input_tokens?: number; output_tokens?: number; cache_read?: number; cache_write?: number; est_usd?: number }
type StatusData = { status?: JobOut['status']; result?: unknown; error?: string }

export function JobProgress({ jobId, onDone }: { jobId: string; onDone?: (j: JobOut) => void }) {
  const { events: progressEvts } = useSSE(`/api/v1/jobs/${jobId}/events/progress`)
  const { events: logEvts } = useSSE(`/api/v1/jobs/${jobId}/events/log`)

  const last = useMemo(() => {
    const out: { progress?: ProgressData; status?: StatusData; cost?: CostData } = {}
    for (const e of progressEvts) {
      if (e.event === 'progress') out.progress = e.data as ProgressData
      else if (e.event === 'status') out.status = e.data as StatusData
      else if (e.event === 'cost') out.cost = e.data as CostData
    }
    return out
  }, [progressEvts])

  // Fall back to polling so we still see terminal status if SSE missed it
  const { data: jobRow } = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => api.getJob(jobId),
    refetchInterval: (q) => {
      const j = q.state.data
      return j && (j.status === 'succeeded' || j.status === 'failed' || j.status === 'cancelled') ? false : 1500
    },
  })

  const status = last.status?.status || jobRow?.status || 'queued'
  const pct = last.progress?.pct
    ?? (last.progress?.total ? Math.round(((last.progress.current ?? 0) / last.progress.total) * 100) : 0)

  const [notified, setNotified] = useState(false)
  useEffect(() => {
    if (!notified && jobRow && (jobRow.status === 'succeeded' || jobRow.status === 'failed' || jobRow.status === 'cancelled')) {
      setNotified(true)
      onDone?.(jobRow)
    }
  }, [jobRow, notified, onDone])

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-2">
        <div className="text-sm">
          <span className={clsx('tag mr-2', {
            'bg-yellow-700': status === 'queued',
            'bg-blue-700': status === 'running',
            'bg-green-700': status === 'succeeded',
            'bg-red-700': status === 'failed',
            'bg-gray-700': status === 'cancelled',
          })}>{status}</span>
          {jobRow?.type} <span className="text-gray-500">· {jobId.slice(0, 8)}</span>
        </div>
        {(status === 'queued' || status === 'running') && (
          <button className="btn-ghost" onClick={() => api.cancelJob(jobId)}>cancel</button>
        )}
        {status === 'failed' && (
          <button className="btn-ghost" onClick={() => api.resumeJob(jobId)}>retry</button>
        )}
      </div>

      <div className="w-full h-2 bg-ink-500 rounded overflow-hidden mb-2">
        <div className={clsx('h-full transition-all', status === 'failed' ? 'bg-red-500' : 'bg-crate-500')}
             style={{ width: `${pct}%` }} />
      </div>
      <div className="text-xs text-gray-400 flex justify-between">
        <span>{last.progress?.current ?? 0} / {last.progress?.total ?? '?'}</span>
        {last.cost && (
          <span>tokens: in {last.cost.input_tokens} · out {last.cost.output_tokens} · cache-r {last.cost.cache_read} · ${last.cost.est_usd?.toFixed(4)}</span>
        )}
      </div>

      {jobRow?.error && (
        <pre className="mt-2 text-xs bg-red-900/40 border border-red-700 rounded p-2 whitespace-pre-wrap">
          {typeof jobRow.error === 'string'
            ? jobRow.error
            : `${jobRow.error.code ?? 'Error'}: ${jobRow.error.message ?? ''}`}
        </pre>
      )}

      <details className="mt-2">
        <summary className="text-xs text-gray-400 cursor-pointer">log ({logEvts.length})</summary>
        <div className="mt-1 max-h-48 overflow-auto bg-ink-900 rounded p-2 font-mono text-xs space-y-0.5">
          {logEvts.map((e, i) => (
            <div key={i} className="text-gray-300">{(e.data as LogData)?.message ?? JSON.stringify(e.data)}</div>
          ))}
        </div>
      </details>

      {jobRow?.result && (
        <details className="mt-2">
          <summary className="text-xs text-gray-400 cursor-pointer">result</summary>
          <pre className="mt-1 text-xs bg-ink-900 rounded p-2 overflow-auto">{JSON.stringify(jobRow.result, null, 2)}</pre>
        </details>
      )}
    </div>
  )
}
