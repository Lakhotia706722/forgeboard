import { Cpu, Plug, Zap } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'

const placeholderStats = [
  { label: 'Active Agents', value: '—', sub: 'Phase 3', icon: Cpu },
  { label: 'Runs Today', value: '—', sub: 'Phase 4', icon: Zap },
  { label: 'Connectors', value: '—', sub: 'Phase 2', icon: Plug },
]

export default function DashboardPage() {
  const user = useAuthStore((s) => s.user)
  const workspace = user?.workspace

  const firstName = user?.full_name?.split(' ')[0] ?? 'there'

  return (
    <div className="max-w-5xl mx-auto px-6 py-10 space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-white">
          Hey, {firstName} 👋
        </h1>
        <p className="mt-1 text-gray-400">
          {workspace
            ? `${workspace.name} — your agent operations board.`
            : 'Your agent operations board.'}
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {placeholderStats.map(({ label, value, sub, icon: Icon }) => (
          <div
            key={label}
            className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-2"
          >
            <div className="flex items-center gap-2 text-gray-500">
              <Icon size={15} aria-hidden="true" />
              <span className="text-sm">{label}</span>
            </div>
            <p className="text-2xl font-bold text-white">{value}</p>
            <p className="text-xs text-gray-700">Live in {sub}</p>
          </div>
        ))}
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Link
          to="/connectors"
          className="flex items-start gap-4 bg-gray-900 border border-gray-800 hover:border-gray-600 rounded-xl p-5 transition-colors group"
        >
          <div className="mt-0.5 p-2 rounded-lg bg-gray-800 group-hover:bg-gray-700 transition-colors">
            <Plug size={18} className="text-forge-400" aria-hidden="true" />
          </div>
          <div>
            <p className="font-semibold text-white">Connect your tools</p>
            <p className="text-sm text-gray-400 mt-0.5">
              Set up Google Calendar, Gmail, webhooks, and more.
            </p>
          </div>
        </Link>

        <Link
          to="/board"
          className="flex items-start gap-4 bg-gray-900 border border-gray-800 hover:border-gray-600 rounded-xl p-5 transition-colors group"
        >
          <div className="mt-0.5 p-2 rounded-lg bg-gray-800 group-hover:bg-gray-700 transition-colors">
            <Cpu size={18} className="text-forge-400" aria-hidden="true" />
          </div>
          <div>
            <p className="font-semibold text-white">Agent board</p>
            <p className="text-sm text-gray-400 mt-0.5">
              View, manage, and deploy all your agents in one place.
            </p>
          </div>
        </Link>
      </div>

      {/* Workspace info */}
      {workspace && (
        <div className="text-xs text-gray-700 border-t border-gray-800 pt-4">
          Workspace: <span className="text-gray-500">{workspace.slug}</span>
          {' · '}
          ID: <span className="font-mono text-gray-500">{workspace.id}</span>
        </div>
      )}
    </div>
  )
}
