import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  Cell, LineChart, Line
} from 'recharts'
import { getDashboardStats, getAlerts, getInvestigations, generateAlert, triggerReplay } from '../../api/client'
import { StatCard, DecisionBadge, StatusBadge, RiskBar, Spinner } from '../../components/shared'

const DECISION_COLOURS = { APPROVE: '#10b981', DENY: '#ef4444', REVIEW: '#f59e0b', PENDING: '#94a3b8' }

function buildThroughputData(recentEvents) {
  // Group events into 1-minute buckets over last 10 minutes
  const now = Date.now()
  const buckets = {}
  for (let i = 9; i >= 0; i--) {
    const label = `${i}m`
    buckets[label] = 0
  }
  for (const e of recentEvents) {
    const age = Math.floor((now - new Date(e.timestamp).getTime()) / 60000)
    if (age >= 0 && age < 10) {
      const label = `${age}m`
      buckets[label] = (buckets[label] || 0) + 1
    }
  }
  return Object.entries(buckets).reverse().map(([t, count]) => ({ t, count }))
}

export function Dashboard() {
  const qc = useQueryClient()
  const [isReplaying, setIsReplaying] = useState(false)

  const { data: stats, isLoading } = useQuery({
    queryKey: ['stats'],
    queryFn: getDashboardStats,
    refetchInterval: 5000,
  })
  const { data: alerts = [] } = useQuery({
    queryKey: ['alerts'],
    queryFn: () => getAlerts(10),
    refetchInterval: 5000,
  })
  const { data: investigations = [] } = useQuery({
    queryKey: ['investigations'],
    queryFn: () => getInvestigations({ limit: 10 }),
    refetchInterval: 5000,
  })

  const generateMutation = useMutation({
    mutationFn: risk => generateAlert(risk),
    onSuccess: () => setTimeout(() => qc.invalidateQueries(), 2000),
  })

  const replayMutation = useMutation({
    mutationFn: async () => {
      setIsReplaying(true)
      const result = await triggerReplay()
      return result
    },
    onSuccess: () => {
      setTimeout(() => {
        setIsReplaying(false)
        qc.invalidateQueries()
      }, 1000)
    },
    onError: () => setIsReplaying(false),
  })

  const decisionChart = stats
    ? Object.entries(stats.decisions || {}).map(([k, v]) => ({ name: k, count: v }))
    : []

  const throughputData = buildThroughputData(stats?.recent_events || [])

  if (isLoading) return <div className="p-6"><Spinner /></div>

  // ── Replay blank state ─────────────────────────────────────────────────────
  if (isReplaying) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-6 bg-slate-50">
        <div className="w-10 h-10 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        <div className="text-center">
          <p className="text-lg font-semibold text-slate-700">Replaying Event Store…</p>
          <p className="text-sm text-slate-500 mt-1">Read models cleared. Rebuilding from events.</p>
          <p className="text-xs text-slate-400 mt-3 font-mono">No agents running. No LLM calls. Pure replay.</p>
        </div>
        <div className="grid grid-cols-4 gap-4 w-full max-w-2xl px-8">
          {['Total Alerts', 'Investigations', 'Pending Review', 'Completed'].map(l => (
            <div key={l} className="bg-white border border-slate-200 rounded-lg p-4">
              <p className="text-xs text-slate-500 mb-1">{l}</p>
              <p className="text-2xl font-semibold text-slate-300">—</p>
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="h-full overflow-auto p-6 space-y-6">

      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-800">Dashboard</h1>
        <div className="flex gap-2">
          {['low', 'medium', 'high', 'random'].map(r => (
            <button key={r} onClick={() => generateMutation.mutate(r)}
              disabled={generateMutation.isPending}
              className={`px-3 py-1.5 rounded text-xs font-medium transition-colors disabled:opacity-50 ${
                r === 'high'   ? 'bg-red-600 hover:bg-red-700 text-white' :
                r === 'medium' ? 'bg-amber-500 hover:bg-amber-600 text-white' :
                r === 'random' ? 'bg-blue-600 hover:bg-blue-700 text-white' :
                                 'bg-emerald-600 hover:bg-emerald-700 text-white'
              }`}>
              {generateMutation.isPending ? '…' : `+ ${r}`}
            </button>
          ))}
          <button onClick={() => replayMutation.mutate()}
            disabled={replayMutation.isPending}
            className="px-3 py-1.5 bg-white border border-slate-200 text-slate-600 rounded text-xs hover:bg-slate-50 transition-colors disabled:opacity-50">
            {replayMutation.isPending ? 'Replaying…' : '↺ Replay'}
          </button>
        </div>
      </div>

      {/* Stat cards — now 5 including Running Workflows */}
      <div className="grid grid-cols-5 gap-4">
        <StatCard label="Total Alerts" value={stats?.total_alerts} />
        <StatCard label="Investigations" value={stats?.total_investigations} />
        <StatCard label="Running Workflows" value={stats?.running_workflows ?? stats?.statuses?.running ?? 0} colour="text-blue-600" />
        <StatCard label="Pending Review" value={stats?.statuses?.pending_review ?? 0} colour="text-amber-600" />
        <StatCard label="Completed" value={stats?.statuses?.completed ?? 0} colour="text-emerald-600" />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-3 gap-4">
        {/* Decision breakdown */}
        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <h2 className="text-sm font-medium text-slate-600 mb-4">Decisions</h2>
          <ResponsiveContainer width="100%" height={140}>
            <BarChart data={decisionChart} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="name" tick={{ fill: '#64748b', fontSize: 11 }} />
              <YAxis tick={{ fill: '#64748b', fontSize: 11 }} />
              <Tooltip contentStyle={{ background: '#fff', border: '1px solid #e2e8f0', color: '#1e293b', fontSize: 12 }} />
              <Bar dataKey="count" radius={[3, 3, 0, 0]}>
                {decisionChart.map(entry => (
                  <Cell key={entry.name} fill={DECISION_COLOURS[entry.name] || '#94a3b8'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Event throughput */}
        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <h2 className="text-sm font-medium text-slate-600 mb-4">Event Throughput (last 10 min)</h2>
          <ResponsiveContainer width="100%" height={140}>
            <LineChart data={throughputData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="t" tick={{ fill: '#64748b', fontSize: 11 }} />
              <YAxis tick={{ fill: '#64748b', fontSize: 11 }} />
              <Tooltip contentStyle={{ background: '#fff', border: '1px solid #e2e8f0', color: '#1e293b', fontSize: 12 }} />
              <Line type="monotone" dataKey="count" stroke="#3b82f6" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Live event feed */}
        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <h2 className="text-sm font-medium text-slate-600 mb-3">Live Event Feed</h2>
          <div className="space-y-1 max-h-44 overflow-auto">
            {(stats?.recent_events || []).slice(0, 15).map(e => (
              <div key={e.event_id} className="flex items-center gap-3 text-xs py-0.5">
                <span className="text-slate-400 font-mono shrink-0">{new Date(e.timestamp).toLocaleTimeString()}</span>
                <span className="font-medium text-blue-700 shrink-0 truncate max-w-36">{e.event_type}</span>
                <span className="text-slate-400 font-mono truncate">{e.aggregate_id?.slice(0, 8)}…</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Tables */}
      <div className="grid grid-cols-2 gap-4">
        {/* Recent Alerts */}
        <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between">
            <h2 className="text-sm font-medium text-slate-600">Recent Alerts</h2>
            <Link to="/alerts" className="text-xs text-blue-600 hover:underline">View all →</Link>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-slate-500">
                <th className="text-left px-4 py-2 text-xs font-medium">ID</th>
                <th className="text-left px-4 py-2 text-xs font-medium">Merchant</th>
                <th className="text-left px-4 py-2 text-xs font-medium">Amount</th>
                <th className="text-left px-4 py-2 text-xs font-medium">Country</th>
                <th className="text-left px-4 py-2 text-xs font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {alerts.length === 0
                ? <tr><td colSpan={5} className="px-4 py-4 text-xs text-slate-400 text-center">No alerts yet</td></tr>
                : alerts.map(a => (
                  <tr key={a.alert_id} className="hover:bg-slate-50">
                    <td className="px-4 py-2 text-xs font-mono text-blue-600">{a.alert_id?.slice(0, 8)}…</td>
                    <td className="px-4 py-2 text-xs text-slate-700">{a.merchant || '—'}</td>
                    <td className="px-4 py-2 text-xs text-slate-700">${a.amount?.toFixed(2)}</td>
                    <td className="px-4 py-2 text-xs text-slate-500">{a.country}</td>
                    <td className="px-4 py-2"><StatusBadge status={a.status} /></td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>

        {/* Recent Investigations */}
        <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between">
            <h2 className="text-sm font-medium text-slate-600">Recent Investigations</h2>
            <Link to="/investigations" className="text-xs text-blue-600 hover:underline">View all →</Link>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-slate-500">
                <th className="text-left px-4 py-2 text-xs font-medium">ID</th>
                <th className="text-left px-4 py-2 text-xs font-medium">Status</th>
                <th className="text-left px-4 py-2 text-xs font-medium">Decision</th>
                <th className="text-left px-4 py-2 text-xs font-medium">Risk</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {investigations.length === 0
                ? <tr><td colSpan={4} className="px-4 py-4 text-xs text-slate-400 text-center">No investigations yet</td></tr>
                : investigations.map(inv => (
                  <tr key={inv.investigation_id} className="hover:bg-slate-50">
                    <td className="px-4 py-2">
                      <Link to={`/investigations/${inv.investigation_id}`}
                        className="text-xs font-mono text-blue-600 hover:underline">
                        {inv.investigation_id?.slice(0, 8)}…
                      </Link>
                    </td>
                    <td className="px-4 py-2"><StatusBadge status={inv.status} /></td>
                    <td className="px-4 py-2"><DecisionBadge decision={inv.decision} /></td>
                    <td className="px-4 py-2"><RiskBar score={inv.risk_score} /></td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
