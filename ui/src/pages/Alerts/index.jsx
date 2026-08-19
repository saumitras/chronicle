import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getAlerts } from '../../api/client'
import { StatusBadge, Spinner } from '../../components/shared'

export function AlertList() {
  const { data = [], isLoading } = useQuery({
    queryKey: ['alerts-full'],
    queryFn: () => getAlerts(100),
    refetchInterval: 5000,
  })

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <div className="px-6 pt-4 pb-3 shrink-0">
        <h1 className="text-xl font-semibold text-slate-800">Alerts</h1>
      </div>
      <div className="flex-1 overflow-auto border-t border-slate-200">
        {isLoading ? <Spinner /> : (
          <table className="w-full text-sm">
            <thead className="sticky top-0">
              <tr className="bg-slate-50 border-b border-slate-200 text-slate-500">
                <th className="text-left px-4 py-2 text-xs font-medium">Alert ID</th>
                <th className="text-left px-4 py-2 text-xs font-medium">Merchant</th>
                <th className="text-left px-4 py-2 text-xs font-medium">Amount</th>
                <th className="text-left px-4 py-2 text-xs font-medium">Country</th>
                <th className="text-left px-4 py-2 text-xs font-medium">VPN</th>
                <th className="text-left px-4 py-2 text-xs font-medium">Status</th>
                <th className="text-left px-4 py-2 text-xs font-medium">Created</th>
                <th className="text-left px-4 py-2 text-xs font-medium">Investigation</th>
              </tr>
            </thead>
            <tbody>
              {data.map(a => (
                <tr key={a.alert_id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-2.5 text-xs font-mono text-slate-600">{a.alert_id?.slice(0,8)}…</td>
                  <td className="px-4 py-2.5 text-xs text-slate-700">{a.merchant || '—'}</td>
                  <td className="px-4 py-2.5 text-xs text-slate-700">${a.amount?.toFixed(2)}</td>
                  <td className="px-4 py-2.5 text-xs text-slate-500">{a.country}</td>
                  <td className="px-4 py-2.5 text-xs">{a.vpn_detected ? <span className="text-red-600">Yes</span> : <span className="text-slate-400">No</span>}</td>
                  <td className="px-4 py-2.5"><StatusBadge status={a.status} /></td>
                  <td className="px-4 py-2.5 text-xs text-slate-500">{new Date(a.created_at).toLocaleTimeString()}</td>
                  <td className="px-4 py-2.5">
                    <Link to={`/investigations/${a.alert_id}`}
                      className="text-xs text-blue-600 hover:underline">View →</Link>
                  </td>
                </tr>
              ))}
              {data.length === 0 && (
                <tr><td colSpan={8} className="px-4 py-8 text-xs text-slate-400 text-center">No alerts yet</td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
