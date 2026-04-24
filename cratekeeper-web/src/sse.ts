import { useEffect, useRef, useState } from 'react'

export type SSEEvent = { id: string; event: string; data: unknown }

/** Subscribe to an SSE channel. Returns the running list of events. */
export function useSSE(url: string | null, options: { maxEvents?: number } = {}) {
  const max = options.maxEvents ?? 200
  const [events, setEvents] = useState<SSEEvent[]>([])
  const [open, setOpen] = useState(false)
  const lastIdRef = useRef<string | null>(null)

  useEffect(() => {
    if (!url) return
    setEvents([])
    lastIdRef.current = null
    const full = new URL(url, window.location.origin)
    const es = new EventSource(full.toString())
    es.onopen = () => setOpen(true)
    es.onerror = () => setOpen(false)
    const handler = (eventName: string) => (e: MessageEvent) => {
      let data: unknown = e.data
      try { data = JSON.parse(e.data) } catch { /* keep raw */ }
      lastIdRef.current = (e as MessageEvent & { lastEventId?: string }).lastEventId || lastIdRef.current
      setEvents((prev) => {
        const next = [...prev, { id: lastIdRef.current || '', event: eventName, data }]
        return next.length > max ? next.slice(-max) : next
      })
    }
    // Backend emits named events (progress / log / status / cost / event-job-...)
    const names = ['progress', 'log', 'status', 'cost', 'checkpoint', 'message']
    names.forEach((n) => es.addEventListener(n, handler(n)))
    es.onmessage = handler('message')
    return () => { es.close(); setOpen(false) }
  }, [url, max])

  return { events, open }
}
