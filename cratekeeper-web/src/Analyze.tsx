import { useMemo } from 'react'
import type { EventTrackOut } from './api'

export function AnalyzePanel({ tracks }: { tracks: EventTrackOut[] }) {
  const analyzed = tracks.filter((t) => t.bpm != null)
  if (analyzed.length === 0) return null

  const energy = useMemo(() => {
    const dist = { low: 0, mid: 0, high: 0 } as Record<string, number>
    analyzed.forEach((t) => {
      if (t.energy && dist[t.energy] != null) dist[t.energy] += 1
    })
    return dist
  }, [analyzed])

  const bpmHist = useMemo(() => {
    const bins = ['<90', '90-100', '100-110', '110-120', '120-130', '130-140', '140+']
    const counts = new Array(bins.length).fill(0) as number[]
    analyzed.forEach((t) => {
      const b = Math.round(t.bpm || 0)
      const idx = b < 90 ? 0 : b < 100 ? 1 : b < 110 ? 2 : b < 120 ? 3 : b < 130 ? 4 : b < 140 ? 5 : 6
      counts[idx] += 1
    })
    return bins.map((label, i) => ({ label, count: counts[i] }))
  }, [analyzed])

  const maxBpm = Math.max(1, ...bpmHist.map((b) => b.count))
  const totalEnergy = energy.low + energy.mid + energy.high || 1

  return (
    <section>
      <h2 className="text-sm uppercase tracking-wide text-gray-400 mb-2">Audio analysis ({analyzed.length})</h2>
      <div className="card grid grid-cols-1 md:grid-cols-2 gap-6 text-xs">
        <div>
          <h3 className="text-gray-300 mb-2">Energy distribution</h3>
          {(['low', 'mid', 'high'] as const).map((k) => (
            <div key={k} className="flex items-center gap-2 mb-1">
              <span className="w-12 text-gray-500">{k}</span>
              <div className="flex-1 bg-ink-500 rounded h-3">
                <div className="bg-crate-500 h-3 rounded" style={{ width: `${(energy[k] / totalEnergy) * 100}%` }} />
              </div>
              <span className="w-10 text-right text-gray-400">{energy[k]}</span>
            </div>
          ))}
        </div>
        <div>
          <h3 className="text-gray-300 mb-2">BPM histogram</h3>
          {bpmHist.map((b) => (
            <div key={b.label} className="flex items-center gap-2 mb-1">
              <span className="w-16 text-gray-500">{b.label}</span>
              <div className="flex-1 bg-ink-500 rounded h-3">
                <div className="bg-crate-500 h-3 rounded" style={{ width: `${(b.count / maxBpm) * 100}%` }} />
              </div>
              <span className="w-10 text-right text-gray-400">{b.count}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
