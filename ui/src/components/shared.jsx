// Decision badge: APPROVE / DENY / REVIEW
export function DecisionBadge({ decision }) {
  if (!decision || decision === 'PENDING') return <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-500">PENDING</span>
  const styles = {
    APPROVE: 'bg-emerald-100 text-emerald-700 border border-emerald-300',
    DENY:    'bg-red-100 text-red-700 border border-red-300',
    REVIEW:  'bg-amber-100 text-amber-700 border border-amber-300',
    EXPIRED: 'bg-slate-100 text-slate-500 border border-slate-300',
  }
  return <span className={`px-2 py-0.5 rounded text-xs font-medium ${styles[decision] || 'bg-slate-100 text-slate-600'}`}>{decision}</span>
}

// Status badge: running / pending_review / completed
export function StatusBadge({ status }) {
  const styles = {
    running:        'bg-blue-100 text-blue-700',
    pending_review: 'bg-amber-100 text-amber-700',
    completed:      'bg-slate-100 text-slate-600',
  }
  return <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${styles[status] || 'bg-slate-100 text-slate-500'}`}>{status?.replace('_', ' ')}</span>
}

// Risk score bar
export function RiskBar({ score }) {
  if (score == null) return <span className="text-xs text-slate-400">—</span>
  const pct = Math.round(score * 100)
  const colour = pct >= 70 ? 'bg-red-500' : pct >= 35 ? 'bg-amber-500' : 'bg-emerald-500'
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 bg-slate-200 rounded-full h-1.5">
        <div className={`h-1.5 rounded-full ${colour}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-slate-500 w-8">{score.toFixed(2)}</span>
    </div>
  )
}

// Stat card
export function StatCard({ label, value, colour = 'text-slate-800' }) {
  return (
    <div className="bg-white border border-slate-200 rounded-lg p-4">
      <p className="text-xs text-slate-500 mb-1">{label}</p>
      <p className={`text-2xl font-semibold ${colour}`}>{value ?? '—'}</p>
    </div>
  )
}

// Loading spinner
export function Spinner() {
  return (
    <div className="flex items-center justify-center py-12">
      <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
    </div>
  )
}

// Event type colour
export function eventColour(type) {
  if (!type) return 'text-slate-500'
  if (type.includes('Completed')) return 'text-emerald-600'
  if (type.includes('Denied') || type.includes('DENY')) return 'text-red-600'
  if (type.includes('Review') || type.includes('REVIEW')) return 'text-amber-600'
  if (type.includes('Started')) return 'text-blue-600'
  if (type.includes('Evidence')) return 'text-violet-600'
  if (type.includes('LLM') || type.includes('Reasoning')) return 'text-cyan-600'
  if (type.includes('Risk') || type.includes('Assessed')) return 'text-orange-600'
  return 'text-slate-600'
}
