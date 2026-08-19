import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getInvestigations } from '../../api/client'
import { DecisionBadge, StatusBadge, RiskBar, Spinner } from '../../components/shared'

function AlertPane({ inv, onClose }) {
  return (
    <div className="w-80 shrink-0 border-l border-slate-200 bg-white flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 shrink-0">
        <div>
          <p className="text-sm font-semibold text-slate-800">{inv.payload?.merchant || 'Alert'}</p>
          <p className="text-xs text-slate-400 font-mono mt-0.5">{inv.investigation_id.slice(0, 8)}…</p>
        </div>
        <button onClick={onClose} className="text-slate-400 hover:text-slate-700 text-xl leading-none">×</button>
      </div>
      <div className="flex-1 overflow-auto p-4 space-y-3">
        <div className="grid grid-cols-2 gap-2">
          {[['Status', <StatusBadge status={inv.status} />], ['Decision', <DecisionBadge decision={inv.decision} />]].map(([l, v]) => (
            <div key={l} className="p-2 bg-slate-50 rounded border border-slate-200">
              <p className="text-xs text-slate-500 mb-1">{l}</p>{v}
            </div>
          ))}
        </div>
        <div>
          <p className="text-xs font-medium text-slate-600 mb-2">Alert Payload</p>
          <pre className="text-xs font-mono bg-slate-900 text-emerald-300 rounded p-3 overflow-auto max-h-64">
            {JSON.stringify(inv.payload || {}, null, 2)}
          </pre>
        </div>
        <Link to={`/investigations/${inv.investigation_id}`}
          className="block w-full text-center px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded text-xs font-medium transition-colors">
          Open Investigation →
        </Link>
      </div>
    </div>
  )
}

export function InvestigationList() {
  const [selected, setSelected] = useState(null)
  const [statusFilter, setStatusFilter] = useState('')
  const { data = [], isLoading } = useQuery({
    queryKey: ['investigations', statusFilter],
    queryFn: () => getInvestigations(statusFilter ? { status: statusFilter, limit: 100 } : { limit: 100 }),
    refetchInterval: 5000,
  })

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <div className="px-6 pt-4 pb-3 shrink-0 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-800">Investigations</h1>
        <div className="flex items-center gap-2">
          {['', 'running', 'pending_review', 'completed'].map(s => (
            <button key={s} onClick={() => setStatusFilter(s)}
              className={`px-3 py-1.5 rounded text-xs transition-colors ${
                statusFilter === s
                  ? 'bg-blue-600 text-white'
                  : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
              }`}>
              {s || 'All'}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-1 min-h-0 border-t border-slate-200">
        <div className="flex-1 overflow-auto">
          {isLoading ? <Spinner /> : (
            <table className="w-full text-sm">
              <thead className="sticky top-0 z-10">
                <tr className="bg-slate-50 border-b border-slate-200 text-slate-500">
                  <th className="text-left px-4 py-2 text-xs font-medium">ID</th>
                  <th className="text-left px-4 py-2 text-xs font-medium">Status</th>
                  <th className="text-left px-4 py-2 text-xs font-medium">Decision</th>
                  <th className="text-left px-4 py-2 text-xs font-medium">Risk</th>
                  <th className="text-left px-4 py-2 text-xs font-medium">Created</th>
                  <th className="text-left px-4 py-2 text-xs font-medium">Details</th>
                </tr>
              </thead>
              <tbody>
                {data.map(inv => {
                  const isSel = selected?.investigation_id === inv.investigation_id
                  return (
                    <tr key={inv.investigation_id}
                      className={`border-b border-slate-100 transition-colors ${isSel ? 'bg-blue-50' : 'hover:bg-slate-50'}`}>
                      <td className="px-4 py-2.5">
                        <Link to={`/investigations/${inv.investigation_id}`}
                          className="text-xs font-mono text-blue-600 hover:underline">
                          {inv.investigation_id.slice(0, 8)}…
                        </Link>
                      </td>
                      <td className="px-4 py-2.5"><StatusBadge status={inv.status} /></td>
                      <td className="px-4 py-2.5"><DecisionBadge decision={inv.decision} /></td>
                      <td className="px-4 py-2.5"><RiskBar score={inv.risk_score} /></td>
                      <td className="px-4 py-2.5 text-xs text-slate-500">
                        {new Date(inv.created_at).toLocaleTimeString()}
                      </td>
                      <td className="px-4 py-2.5">
                        <button onClick={() => setSelected(isSel ? null : inv)}
                          className={`text-xs px-2 py-0.5 rounded border transition-colors ${
                            isSel ? 'bg-blue-100 text-blue-700 border-blue-300' : 'bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100'
                          }`}>View</button>
                      </td>
                    </tr>
                  )
                })}
                {data.length === 0 && (
                  <tr><td colSpan={6} className="px-4 py-8 text-xs text-slate-400 text-center">No investigations</td></tr>
                )}
              </tbody>
            </table>
          )}
        </div>
        {selected && <AlertPane inv={selected} onClose={() => setSelected(null)} />}
      </div>
    </div>
  )
}
