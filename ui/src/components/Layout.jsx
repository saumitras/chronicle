import { Link, useLocation } from 'react-router-dom'

const links = [
  { to: '/', label: 'Dashboard' },
  { to: '/investigations', label: 'Investigations' },
  { to: '/alerts', label: 'Alerts' },
]

export function Layout({ children }) {
  const { pathname } = useLocation()
  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <header className="bg-blue-900 px-5 h-12 flex items-center justify-between text-white shrink-0">
        <div className="flex items-center gap-4">
          <div className="w-7 h-7 bg-blue-600 border-2 border-blue-400 rounded-lg flex items-center justify-center text-xs font-bold">
            C
          </div>
          <span className="text-sm font-semibold tracking-wide">Chronicle</span>
          <nav className="flex items-center gap-1 ml-4">
            {links.map(l => (
              <Link key={l.to} to={l.to}
                className={`px-3 py-1.5 rounded text-sm transition-colors ${
                  (l.to === '/' ? pathname === '/' : pathname.startsWith(l.to))
                    ? 'bg-blue-700 text-white font-medium'
                    : 'text-blue-200 hover:bg-blue-800 hover:text-white'
                }`}>
                {l.label}
              </Link>
            ))}
          </nav>
        </div>
        <div className="w-7 h-7 bg-blue-600 border-2 border-blue-400 rounded-full flex items-center justify-center text-xs font-medium">
          A
        </div>
      </header>
      <main className="flex-1 overflow-hidden">
        {children}
      </main>
    </div>
  )
}
