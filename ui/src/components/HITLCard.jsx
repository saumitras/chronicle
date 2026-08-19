import { useState } from 'react'
import { submitDecision, submitClarify } from '../api/client'
import { RiskBar, DecisionBadge } from './shared'

export function HITLCard({ investigationId, onResolved, derivedState }) {
  const [mode, setMode] = useState('review')
  const [reviewerId, setReviewerId] = useState('dashboard-reviewer')
  const [comment, setComment] = useState('')
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function decide(decision) {
    setLoading(true); setError('')
    try {
      await submitDecision(investigationId, { reviewer_id: reviewerId, decision, comment })
      onResolved?.()
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  async function clarify() {
    setLoading(true); setError(''); setAnswer(null)
    try {
      const r = await submitClarify(investigationId, { reviewer_id: reviewerId, question })
      setAnswer(r.answer)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  const device = derivedState?.deviceEvidence
  const geo = derivedState?.geoEvidence
  const customer = derivedState?.customerEvidence
  const allFlags = [
    ...(device?.risk_flags || []),
    ...(geo?.risk_flags || []),
    ...(customer?.risk_flags || []),
  ]

  return (
    <div className="bg-amber-50 border border-amber-300 rounded-lg overflow-hidden">
      {/* Header */}
      <div className="px-4 py-2 bg-amber-100 border-b border-amber-200 flex items-center gap-2">
        <span className="text-amber-700 font-semibold text-sm">⏸ Awaiting Human Review</span>
        {derivedState?.riskScore != null && (
          <div className="ml-auto flex items-center gap-2">
            <RiskBar score={derivedState.riskScore} />
            <DecisionBadge decision="REVIEW" />
          </div>
        )}
      </div>

      <div className="p-4 space-y-3">
        {/* Evidence summary */}
        <div className="grid grid-cols-3 gap-2">
          {device && (
            <div className="bg-white rounded border border-slate-200 p-2">
              <p className="text-xs font-semibold text-slate-600 mb-1">💻 Device</p>
              <p className="text-xs text-slate-500">Known: <span className={`font-medium ${device.known ? 'text-emerald-600' : 'text-red-600'}`}>{device.known ? 'Yes' : 'No'}</span></p>
              <p className="text-xs text-slate-500">Fraud flags: <span className="font-medium text-slate-700">{device.fraud_flags}</span></p>
            </div>
          )}
          {geo && (
            <div className="bg-white rounded border border-slate-200 p-2">
              <p className="text-xs font-semibold text-slate-600 mb-1">🌍 Geo</p>
              <p className="text-xs text-slate-500">Country: <span className="font-medium text-slate-700">{geo.country} ({geo.country_risk})</span></p>
              <p className="text-xs text-slate-500">VPN: <span className={`font-medium ${geo.vpn_detected ? 'text-red-600' : 'text-emerald-600'}`}>{geo.vpn_detected ? 'Detected' : 'None'}</span></p>
            </div>
          )}
          {customer && (
            <div className="bg-white rounded border border-slate-200 p-2">
              <p className="text-xs font-semibold text-slate-600 mb-1">👤 Customer</p>
              <p className="text-xs text-slate-500">Ratio: <span className="font-medium text-slate-700">{customer.amount_ratio}x avg</span></p>
              <p className="text-xs text-slate-500">Prior alerts: <span className="font-medium text-slate-700">{customer.prior_alerts}</span></p>
            </div>
          )}
        </div>

        {/* Risk flags */}
        {allFlags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {allFlags.map(f => (
              <span key={f} className="px-1.5 py-0.5 bg-red-100 text-red-700 rounded text-xs">{f.replace(/_/g, ' ')}</span>
            ))}
          </div>
        )}

        {/* LLM reasoning */}
        {derivedState?.llmReasoning && (
          <div className="bg-blue-50 border border-blue-200 rounded p-2">
            <p className="text-xs font-semibold text-blue-700 mb-1">⚡ LLM Assessment</p>
            <p className="text-xs text-slate-700 leading-relaxed">{derivedState.llmReasoning}</p>
          </div>
        )}

        {error && <p className="text-red-500 text-xs">{error}</p>}

        {/* Actions */}
        {mode === 'review' && (
          <>
            <div className="flex gap-2">
              <input value={reviewerId} onChange={e => setReviewerId(e.target.value)}
                className="bg-white border border-slate-200 rounded px-2 py-1 text-xs w-36 focus:outline-none focus:border-blue-400"
                placeholder="Reviewer ID" />
              <input value={comment} onChange={e => setComment(e.target.value)}
                className="bg-white border border-slate-200 rounded px-2 py-1 text-xs flex-1 focus:outline-none focus:border-blue-400"
                placeholder="Comment (optional)" />
            </div>
            <div className="flex gap-2">
              <button onClick={() => decide('approve')} disabled={loading}
                className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-medium disabled:opacity-50">
                ✓ Approve
              </button>
              <button onClick={() => decide('deny')} disabled={loading}
                className="px-3 py-1.5 bg-red-600 hover:bg-red-500 text-white rounded text-xs font-medium disabled:opacity-50">
                ✗ Deny
              </button>
              <button onClick={() => setMode('clarify')}
                className="px-3 py-1.5 bg-white border border-slate-200 text-slate-600 rounded text-xs hover:bg-slate-50">
                ? Clarify
              </button>
            </div>
          </>
        )}

        {mode === 'clarify' && (
          <div className="space-y-2">
            <textarea value={question} onChange={e => setQuestion(e.target.value)}
              placeholder="Ask a question about this investigation…"
              className="w-full h-16 bg-white border border-slate-300 rounded p-2 text-xs focus:outline-none focus:border-blue-400 resize-none" />
            <div className="flex gap-2">
              <button onClick={clarify} disabled={loading || !question}
                className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded text-xs font-medium disabled:opacity-50">
                {loading ? 'Asking…' : 'Get Answer'}
              </button>
              <button onClick={() => { setMode('review'); setAnswer(null) }}
                className="px-3 py-1.5 bg-white border border-slate-200 text-slate-600 rounded text-xs hover:bg-slate-50">
                Back
              </button>
            </div>
            {answer && (
              <div className="bg-blue-50 border border-blue-200 rounded p-3 space-y-1">
                <div className="text-xs font-semibold text-blue-700">⚡ AI Answer</div>
                <p className="text-xs text-slate-500 italic">"{question}"</p>
                <p className="text-xs text-slate-800 leading-relaxed whitespace-pre-wrap">{answer}</p>
                <p className="text-xs text-slate-400 mt-1">Workflow remains paused — use Approve / Deny above.</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
