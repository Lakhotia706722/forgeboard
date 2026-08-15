import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Building2, Cpu, Zap, Phone, ChevronRight, Copy } from 'lucide-react'
import toast from 'react-hot-toast'

import AppShell from '@/components/layout/AppShell'
import { agencyApi, type AgencyWorkspaceSummary } from '@/lib/agencyApi'
import { useAuthStore } from '@/store/authStore'
import { cn } from '@/lib/utils'

// ---------------------------------------------------------------------------
// Clone agent modal
// ---------------------------------------------------------------------------
interface CloneModalProps {
  workspaces: AgencyWorkspaceSummary[]
  onClose: () => void
}

function CloneAgentModal({ workspaces, onClose }: CloneModalProps) {
  const qc = useQueryClient()
  const [sourceWsId, setSourceWsId] = useState(workspaces[0]?.workspace_id ?? '')
  const [agentId, setAgentId] = useState('')
  const [destWsId, setDestWsId] = useState('')
  const [destName, setDestName] = useState('')

  const cloneMutation = useMutation({
    mutationFn: agencyApi.cloneAgent,
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['agency-dashboard'] })
      toast.success(`Cloned as "${res.cloned_name}" — it's in Draft in the destination workspace.`)
      onClose()
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Clone failed.'),
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!agentId.trim() || !destWsId) return
    cloneMutation.mutate({
      source_workspace_id: sourceWsId,
      source_agent_id: agentId.trim(),
      dest_workspace_id: destWsId,
      dest_name: destName.trim() || undefined,
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} aria-hidden="true" />
      <div className="relative z-50 bg-gray-900 border border-gray-700 rounded-2xl p-6 w-full max-w-md shadow-2xl">
        <h2 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
          <Copy size={15} className="text-forge-400" aria-hidden="true" />
          Clone Agent Across Workspaces
        </h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Source workspace</label>
            <select
              value={sourceWsId}
              onChange={(e) => setSourceWsId(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:ring-1 focus:ring-forge-500"
              aria-label="Source workspace"
            >
              {workspaces.map((ws) => (
                <option key={ws.workspace_id} value={ws.workspace_id}>
                  {ws.workspace_name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs text-gray-500 mb-1">
              Source agent ID
              <span className="ml-1 text-gray-600">(UUID from the agent board)</span>
            </label>
            <input
              type="text"
              value={agentId}
              onChange={(e) => setAgentId(e.target.value)}
              placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              required
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 font-mono placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-forge-500"
              aria-label="Source agent ID"
            />
          </div>

          <div>
            <label className="block text-xs text-gray-500 mb-1">Destination workspace</label>
            <select
              value={destWsId}
              onChange={(e) => setDestWsId(e.target.value)}
              required
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:ring-1 focus:ring-forge-500"
              aria-label="Destination workspace"
            >
              <option value="">Select destination…</option>
              {workspaces
                .filter((ws) => ws.workspace_id !== sourceWsId)
                .map((ws) => (
                  <option key={ws.workspace_id} value={ws.workspace_id}>
                    {ws.workspace_name}
                  </option>
                ))}
            </select>
          </div>

          <div>
            <label className="block text-xs text-gray-500 mb-1">
              Clone name <span className="text-gray-600">(optional)</span>
            </label>
            <input
              type="text"
              value={destName}
              onChange={(e) => setDestName(e.target.value)}
              placeholder="Defaults to original name + (clone)"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-forge-500"
              aria-label="Cloned agent name"
            />
          </div>

          <p className="text-xs text-gray-600">
            Only the agent config is copied (name, goal, trigger). Run history and connectors are not
            transferred — you'll need to add connectors in the destination workspace.
          </p>

          <div className="flex gap-2 pt-1">
            <button
              type="submit"
              disabled={!agentId.trim() || !destWsId || cloneMutation.isPending}
              className="flex-1 py-2 text-sm bg-forge-600 hover:bg-forge-500 disabled:opacity-50 text-white rounded-lg transition-colors"
            >
              {cloneMutation.isPending ? 'Cloning…' : 'Clone agent'}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-500 hover:text-gray-300 transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function AgencyDashboardPage() {
  const [showClone, setShowClone] = useState(false)
  const user = useAuthStore((s) => s.user)

  const { data: dashboard, isLoading } = useQuery({
    queryKey: ['agency-dashboard'],
    queryFn: agencyApi.getDashboard,
  })

  const isAgency = user?.workspaces.some((w) => w.role === 'agency')

  const stats = dashboard
    ? [
        {
          label: 'Managed workspaces',
          value: dashboard.managed_workspace_count,
          icon: Building2,
          color: 'text-forge-400',
        },
        {
          label: 'Total agents',
          value: dashboard.total_agents,
          sub: `${dashboard.total_live_agents} live`,
          icon: Cpu,
          color: 'text-blue-400',
        },
        {
          label: 'Runs (7d)',
          value: dashboard.total_runs_last_7d,
          icon: Zap,
          color: 'text-green-400',
        },
        {
          label: 'Voice escalations',
          value: dashboard.total_escalations,
          icon: Phone,
          color: dashboard.total_escalations > 0 ? 'text-amber-400' : 'text-gray-600',
        },
      ]
    : []

  return (
    <AppShell>
      <div className="max-w-5xl mx-auto px-6 py-8 space-y-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-white flex items-center gap-2">
              <Building2 size={18} className="text-forge-400" aria-hidden="true" />
              Agency Dashboard
            </h1>
            <p className="text-sm text-gray-500 mt-0.5">
              Aggregate view across all managed client workspaces.
            </p>
          </div>
          {isAgency && dashboard && dashboard.workspaces.length > 1 && (
            <button
              onClick={() => setShowClone(true)}
              className="flex items-center gap-1.5 px-4 py-2 text-sm bg-forge-600 hover:bg-forge-500 text-white rounded-lg transition-colors"
            >
              <Copy size={13} aria-hidden="true" />
              Clone agent
            </button>
          )}
        </div>

        {!isAgency && (
          <div className="bg-amber-900/20 border border-amber-800 rounded-xl px-5 py-4 text-sm text-amber-300">
            Your account does not have agency membership in any workspace yet. Ask a workspace owner to
            invite you with the <span className="font-mono font-medium">agency</span> role.
          </div>
        )}

        {isLoading && (
          <div className="flex items-center justify-center py-16 text-gray-600">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-gray-700 border-t-forge-500" />
          </div>
        )}

        {/* Stats */}
        {!isLoading && dashboard && (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {stats.map(({ label, value, sub, icon: Icon, color }) => (
                <div
                  key={label}
                  className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-2"
                >
                  <div className={cn('flex items-center gap-1.5 text-xs', color)}>
                    <Icon size={13} aria-hidden="true" />
                    <span className="text-gray-500">{label}</span>
                  </div>
                  <p className="text-2xl font-bold text-white">{value}</p>
                  {sub && <p className="text-xs text-gray-600">{sub}</p>}
                </div>
              ))}
            </div>

            {/* Workspace table */}
            {dashboard.workspaces.length > 0 ? (
              <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
                <div className="px-4 py-3 border-b border-gray-800">
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    Client Workspaces
                  </p>
                </div>
                <table className="w-full text-sm" role="table" aria-label="Managed client workspaces">
                  <thead>
                    <tr className="border-b border-gray-800 bg-gray-900/60">
                      {['Workspace', 'Agents', 'Live', ''].map((h) => (
                        <th
                          key={h}
                          className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider"
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {dashboard.workspaces.map((ws, i) => (
                      <tr
                        key={ws.workspace_id}
                        className={cn(
                          'border-b border-gray-800/60 hover:bg-gray-800/30 transition-colors',
                          i === dashboard.workspaces.length - 1 && 'border-b-0',
                        )}
                      >
                        <td className="px-4 py-3">
                          <p className="font-medium text-gray-200">{ws.workspace_name}</p>
                          <p className="text-xs text-gray-600 font-mono">{ws.workspace_slug}</p>
                        </td>
                        <td className="px-4 py-3 text-gray-400">{ws.agent_count}</td>
                        <td className="px-4 py-3">
                          <span
                            className={cn(
                              'text-sm font-medium',
                              ws.live_agent_count > 0 ? 'text-green-400' : 'text-gray-600',
                            )}
                          >
                            {ws.live_agent_count}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            onClick={() => {
                              useAuthStore.getState().setActiveWorkspace(ws.workspace_id)
                              toast.success(`Switched to ${ws.workspace_name}`)
                            }}
                            className="text-xs text-gray-600 hover:text-forge-400 transition-colors flex items-center gap-0.5 ml-auto"
                            aria-label={`Switch to ${ws.workspace_name}`}
                          >
                            Switch
                            <ChevronRight size={11} aria-hidden="true" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center py-16 text-gray-600">
                <Building2 size={32} className="mx-auto mb-3 opacity-30" aria-hidden="true" />
                <p className="text-sm">No managed workspaces yet.</p>
                <p className="text-xs text-gray-700 mt-1">
                  Ask workspace owners to add you with the <span className="font-mono">agency</span> role.
                </p>
              </div>
            )}
          </>
        )}
      </div>

      {showClone && dashboard && (
        <CloneAgentModal
          workspaces={dashboard.workspaces}
          onClose={() => setShowClone(false)}
        />
      )}
    </AppShell>
  )
}
