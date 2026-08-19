import { useState, useEffect, useRef } from 'react'

const SSE_URL = (import.meta.env.VITE_API_URL || '/api') + '/../stream'

export function useInvestigationStream(investigationId) {
  const [events, setEvents] = useState([])
  const [isConnected, setIsConnected] = useState(false)
  const esRef = useRef(null)

  useEffect(() => {
    if (!investigationId) return
    const url = '/stream'
    const es = new EventSource(url)
    esRef.current = es

    es.onopen = () => setIsConnected(true)
    es.onerror = () => setIsConnected(false)
    es.onmessage = e => {
      try {
        const event = JSON.parse(e.data)
        if (event.aggregate_id === investigationId) {
          setEvents(prev => {
            if (prev.find(x => x.event_id === event.event_id)) return prev
            return [...prev, event].sort((a, b) => a.stream_version - b.stream_version)
          })
        }
      } catch {}
    }
    return () => { es.close(); setIsConnected(false) }
  }, [investigationId])

  return { events, isConnected }
}
