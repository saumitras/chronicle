import { useState, useMemo, useEffect, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getInvestigation, getInvestigationEvents } from '../../api/client'
import { useInvestigationStream } from '../../hooks/useInvestigationStream'
import { useDerivedState } from '../../hooks/useDerivedState'
import { DecisionBadge, StatusBadge, RiskBar, Spinner, eventColour } from '../../components/shared'
import { HITLCard } from '../../components/HITLCard'
import { Scrubber } from '../../components/Scrubber'

// ── Evidence card ──────────────────────────────────────────────────────────────
function EvidenceCard({ title, icon, evidence, colour = 'border-slate-200' }) {
  if (!evidence) return (
    <div className={`bg-white border ${colour} rounded p-3 opacity-40`}>
      <div className="text-xs font-medium text-slate-500">{icon} {title}</div>
      <p className="text-xs text-slate-400 mt-1">Waiting…</p>
    </div>
  )
  return (
    <div className={`bg-white border ${colour} rounded p-3`}>
      <div className="text-xs font-semibold text-slate-700 mb-2">{icon} {title}</div>
      {Object.entries(evidence).filter(([k]) => k !== 'risk_flags').map(([k, v]) => (
        <div key={k} className="flex justify-between text-xs mb-0.5">
          <span className="text-slate-500">{k.replace(/_/g, ' ')}</span>
          <span className="text-slate-700 font-medium">{String(v)}</span>
        </div>
      ))}
      {evidence.risk_flags?.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {evidence.risk_flags.map(f => (
            <span key={f} className="px-1.5 py-0.5 bg-red-100 text-red-700 rounded text-xs">{f.replace(/_/g, ' ')}</span>
          ))}
        </div>
      )}
    </div>
  )
}

export function InvestigationDetail() {
  const { id } = useParams()
  const qc = useQueryClient()
  const [selectedEvent, setSelectedEvent] = useState(null)
  const [scrubTs, setScrubTs] = useState(undefined)
  const [isPlaying, setIsPlaying] = useState(false)
  const playRef = useRef(null)

  const { data: inv, refetch: refetchInv } = useQuery({
    queryKey: ['investigation', id],
    queryFn: () => getInvestigation(id),
    enabled: !!id, refetchInterval: 3000,
  })

  const { data: historicalEvents = [] } = useQuery({
    queryKey: ['inv-events', id],
    queryFn: () => getInvestigationEvents(id),
    enabled: !!id, refetchInterval: 5000,
  })

  const { events: liveEvents, isConnected } = useInvestigationStream(id)

  const allEvents = useMemo(() => {
    const seen = new Set()
    const merged = []
    for (const e of [...historicalEvents, ...liveEvents]) {
      if (!seen.has(e.event_id)) { seen.add(e.event_id); merged.push(e) }
    }
    return merged.sort((a, b) => a.stream_version - b.stream_version)
  }, [historicalEvents, liveEvents])

  const derivedState = useDerivedState(allEvents, scrubTs)
  const isLive = inv?.status === 'running' || inv?.status === 'pending_review'
  const visibleEvents = scrubTs
    ? allEvents.filter(e => new Date(e.timestamp).getTime() <= scrubTs)
    : allEvents

  // Play animation
  useEffect(() => {
    if (!isPlaying || allEvents.length === 0) { clearInterval(playRef.current); return }
    const ts = allEvents.filter(e => e.timestamp).map(e => new Date(e.timestamp).getTime()).sort((a, b) => a - b)
    if (!ts.length) return
    const minTs = ts[0], maxTs = ts[ts.length - 1], range = maxTs - minTs || 1
    const step = (range / 6000) * 50
    let current = (scrubTs && scrubTs >= minTs && scrubTs < maxTs) ? scrubTs : minTs
    playRef.current = setInterval(() => {
      current += step
      if (current >= maxTs) { setScrubTs(maxTs); setIsPlaying(false); clearInterval(playRef.current); return }
      setScrubTs(current)
    }, 50)
    return () => clearInterval(playRef.current)
  }, [isPlaying]) // eslint-disable-line

  return (
    <div className="flex flex-col h-full overflow-hidden">

      {/* Header bar */}
      <div className="px-4 py-2 bg-white border-b border-slate-200 shrink-0 flex items-center gap-4">
        <span className="text-xs font-mono text-slate-500">{id?.slice(0, 8)}…</span>
        <StatusBadge status={inv?.status} />
        <DecisionBadge decision={inv?.decision} />
        <RiskBar score={inv?.risk_score} />
        {inv?.workflow_id && (
          <a
            href={`/temporal/namespaces/default/workflows/${inv.workflow_id}`}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 border border-blue-200 hover:border-blue-400 rounded px-2 py-0.5 transition-colors font-mono"
            title="Open in Temporal UI"
          >
            ⚡ {inv.workflow_id.slice(0, 20)}…
          </a>
        )}
        {/* Historical badge — shown for seeded investigations */}
        {allEvents.some(e => e.payload?.model === 'historical') && (
          <span className="px-2 py-0.5 bg-slate-100 text-slate-500 rounded text-xs border border-slate-200">Historical</span>
        )}
        <span className={`flex items-center gap-1 text-xs ml-auto ${isLive && isConnected ? 'text-emerald-600' : 'text-slate-400'}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${isLive && isConnected ? 'bg-emerald-500 animate-pulse' : 'bg-slate-300'}`} />
          {isLive ? (isConnected ? 'Live' : 'Connecting…') : 'Historical'}
        </span>
        <span className="text-xs text-slate-400">{allEvents.length} events</span>
      </div>

      {/* Three panes */}
      <div className="flex flex-1 min-h-0 overflow-hidden">

        {/* Pane 1: Event Timeline */}
        <div className="w-64 shrink-0 border-r border-slate-200 flex flex-col bg-white">
          <div className="px-3 py-2 border-b border-slate-100 shrink-0">
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Event Timeline</p>
          </div>
          <div className="flex-1 overflow-auto">
            {visibleEvents.map(e => {
              const isSelected = selectedEvent?.event_id === e.event_id
              return (
                <div key={e.event_id} onClick={() => setSelectedEvent(isSelected ? null : e)}
                  className={`px-3 py-2 border-b border-slate-100 cursor-pointer transition-colors ${isSelected ? 'bg-blue-50' : 'hover:bg-slate-50'}`}>
                  <div className="flex items-center gap-2">
                    <span className="text-slate-300 text-xs w-4 shrink-0">{e.stream_version}</span>
                    <span className={`text-xs font-medium truncate ${eventColour(e.event_type)}`}>
                      {e.event_type.replace(/([A-Z])/g, ' $1').trim()}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5 ml-6">
                    {new Date(e.timestamp).toLocaleTimeString()}
                  </p>
                </div>
              )
            })}
            {allEvents.length === 0 && (
              <p className="text-xs text-slate-400 text-center py-8">Waiting for events…</p>
            )}
          </div>
          <Scrubber events={allEvents} currentTs={scrubTs}
            onSeek={ts => { setScrubTs(ts); setIsPlaying(false) }}
            onPlay={() => { if (scrubTs && scrubTs >= Math.max(...allEvents.map(e => new Date(e.timestamp).getTime()))) setScrubTs(undefined); setIsPlaying(p => !p) }}
            isPlaying={isPlaying} />
        </div>

        {/* Pane 2: Current State */}
        <div className="flex-1 overflow-auto p-4 space-y-3 min-w-0">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-3">Investigation State</p>

          {/* HITL card */}
          {derivedState.status === 'pending_review' && !scrubTs && (
            <HITLCard
              investigationId={id}
              derivedState={derivedState}
              onResolved={() => { refetchInv(); qc.invalidateQueries(['inv-events', id]) }}
            />
          )}

          {/* Evidence cards */}
          <EvidenceCard title="Device Evidence" icon="💻" evidence={derivedState.deviceEvidence}
            colour={derivedState.deviceEvidence ? 'border-violet-200' : 'border-slate-200'} />
          <EvidenceCard title="Geo Evidence" icon="🌍" evidence={derivedState.geoEvidence}
            colour={derivedState.geoEvidence ? 'border-blue-200' : 'border-slate-200'} />
          <EvidenceCard title="Customer Evidence" icon="👤" evidence={derivedState.customerEvidence}
            colour={derivedState.customerEvidence ? 'border-cyan-200' : 'border-slate-200'} />

          {/* LLM Reasoning */}
          {derivedState.llmReasoning ? (
            <div className="bg-blue-50 border border-blue-200 rounded p-3 space-y-2">
              <div className="text-xs font-semibold text-blue-700">⚡ LLM Reasoning</div>
              <p className="text-xs text-slate-700 leading-relaxed">{derivedState.llmReasoning}</p>
              {derivedState.riskFlags.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {derivedState.riskFlags.map(f => (
                    <span key={f} className="px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">{f.replace(/_/g, ' ')}</span>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="bg-blue-50 border border-blue-200 rounded p-3 opacity-40">
              <div className="text-xs font-semibold text-blue-700">⚡ LLM Reasoning</div>
              <p className="text-xs text-slate-400 mt-1">Waiting…</p>
            </div>
          )}

          {/* Risk assessment */}
          {derivedState.riskScore != null && (
            <div className="bg-white border border-slate-200 rounded p-3">
              <div className="text-xs font-semibold text-slate-700 mb-2">📊 Risk Assessment</div>
              <div className="flex items-center justify-between">
                <RiskBar score={derivedState.riskScore} />
                <DecisionBadge decision={derivedState.decision} />
              </div>
            </div>
          )}
        </div>

        {/* Pane 3: Event detail or system activity */}
        <div className="w-72 shrink-0 border-l border-slate-200 bg-white flex flex-col">
          {selectedEvent ? (
            <>
              <div className="px-3 py-2 border-b border-slate-100 flex items-center justify-between shrink-0">
                <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Event Detail</p>
                <button onClick={() => setSelectedEvent(null)} className="text-slate-400 hover:text-slate-600 text-sm">×</button>
              </div>
              <div className="flex-1 overflow-auto p-3 space-y-3">
                <div>
                  <p className={`text-sm font-semibold ${eventColour(selectedEvent.event_type)}`}>
                    {selectedEvent.event_type}
                  </p>
                  <p className="text-xs text-slate-400 mt-0.5">{new Date(selectedEvent.timestamp).toLocaleString()}</p>
                </div>
                {[
                  ['Producer', selectedEvent.producer],
                  ['Stream Version', selectedEvent.stream_version],
                  ['Correlation ID', selectedEvent.correlation_id],
                  ['Causation ID', selectedEvent.causation_id],
                ].map(([l, v]) => v ? (
                  <div key={l}>
                    <p className="text-xs text-slate-500">{l}</p>
                    <p className="text-xs text-slate-700 font-mono break-all">{v}</p>
                  </div>
                ) : null)}
                {selectedEvent.workflow_id && (
                  <div>
                    <p className="text-xs text-slate-500">Workflow ID</p>
                    <a
                      href={`/temporal/namespaces/default/workflows/${selectedEvent.workflow_id}`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-blue-600 hover:underline font-mono break-all"
                    >
                      {selectedEvent.workflow_id}
                    </a>
                  </div>
                )}
                {/* Kafka metadata */}
                {selectedEvent.payload?.kafka && (
                  <div className="bg-slate-50 border border-slate-200 rounded p-2 space-y-1">
                    <p className="text-xs font-semibold text-slate-600">Kafka</p>
                    {[['Topic', selectedEvent.payload.kafka.topic],
                      ['Partition', selectedEvent.payload.kafka.partition],
                      ['Offset', selectedEvent.payload.kafka.offset],
                    ].map(([l, v]) => (
                      <div key={l} className="flex justify-between text-xs">
                        <span className="text-slate-500">{l}</span>
                        <span className="text-slate-700 font-mono">{v}</span>
                      </div>
                    ))}
                  </div>
                )}
                <div>
                  <p className="text-xs text-slate-500 mb-1">Payload</p>
                  <pre className="text-xs font-mono bg-slate-900 text-emerald-300 rounded p-2 overflow-auto max-h-64">
                    {JSON.stringify(selectedEvent.payload, null, 2)}
                  </pre>
                </div>
              </div>
            </>
          ) : (
            <>
              <div className="px-3 py-2 border-b border-slate-100 shrink-0">
                <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">System Activity</p>
              </div>
              <div className="flex-1 overflow-auto p-3 space-y-1">
                {allEvents.slice().reverse().map(e => (
                  <div key={e.event_id} className="text-xs py-1 border-b border-slate-50">
                    <div className="flex gap-2 items-center">
                      <span className="text-slate-300 shrink-0 w-4">{e.stream_version}</span>
                      <span className={`font-medium truncate ${eventColour(e.event_type)}`}>{e.event_type}</span>
                    </div>
                    <div className="flex gap-2 mt-0.5 ml-6 text-slate-400">
                      <span>{e.producer}</span>
                      <span>·</span>
                      <span>{new Date(e.timestamp).toLocaleTimeString()}</span>
                    </div>
                    {e.workflow_id && (
                      <a
                        href={`/temporal/namespaces/default/workflows/${e.workflow_id}`}
                        target="_blank"
                        rel="noreferrer"
                        className="text-blue-400 hover:text-blue-600 font-mono ml-6 truncate block text-xs"
                      >
                        {e.workflow_id}
                      </a>
                    )}
                  </div>
                ))}
                {allEvents.length === 0 && (
                  <p className="text-xs text-slate-400 text-center py-8">No activity yet</p>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
