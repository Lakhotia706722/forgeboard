import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, LayoutGrid, List } from 'lucide-react'
import toast from 'react-hot-toast'

import { agentApi, type AgentOut, type AgentStatus } from '@/lib/agentApi'
import { connectorApi } from '@/lib/connectorApi'
import { runApi, type RunOut } from '@/lib/runApi'
import { voiceApi, type VoiceAgentOut } from '@/lib/voiceApi'
import Button from '@/components/ui/Button'
import AgentRow from '@/components/agents/AgentRow'
import AgentBuilderModal from '@/components/agents/AgentBuilderModal'
import KanbanBoard from '@/components/board/KanbanBoard'
import AgentDetailDrawer from '@/components/board/AgentDetailDrawer'
import { cn } from '@/lib/utils'

type ViewMode = 'kanban' | 'list'

export default function BoardPage() {
  const queryClient = useQueryClient()
  const [viewMode, setViewMode] = useState<ViewMode>('kanban')
  const [showBuilder, setShowBuilder] = useState(false)
  const [editingAgent, setEditingAgent] = useState<AgentOut | undefined>(undefined)
  const [detailAgent, setDetailAgent] = useState<AgentOut | null>(null)

  const { data: agents = [], isLoading: agentsLoading } = useQuery({
    queryKey: ['agents'],
    queryFn: agentApi.list,
  })

  const { data: connectors = [] } = useQuery({
    queryKey: ['connectors'],
    queryFn: connectorApi.list,
  })

  // Fetch recent runs to show last-run status on cards
  const { data: recentRuns = [] } = useQuery({
    queryKey: ['runs-recent'],
    queryFn: () => runApi.listAll(200),
    refetchInterval: 15000,
  })

  // Fetch voice agents — parallel with agents query
  const { data: voiceAgents = [] } = useQuery({
    queryKey: ['voice-agents'],
    queryFn: voiceApi.listVoiceAgents,
    refetchInterval: 30000,
  })

  // Build maps
  // agentId → most recent run
  const lastRunByAgent: Record<string, RunOut> = {}
  for (const run of recentRuns) {
    if (!lastRunByAgent[run.agent_id]) {
      lastRunByAgent[run.agent_id] = run
    }
  }

  // agentId → VoiceAgentOut (for conditional card rendering on the board)
  const voiceAgentsByAgentId: Record<string, VoiceAgentOut> = {}
  for (const va of voiceAgents) {
    voiceAgentsByAgentId[va.agent_id] = va
  }

  // ── Mutation helpers ──────────────────────────────────────────────────────

  function setAgents(next: AgentOut[]) {
    queryClient.setQueryData<AgentOut[]>(['agents'], next)
  }

  function upsertAgent(agent: AgentOut) {
    queryClient.setQueryData<AgentOut[]>(['agents'], (prev) => {
      if (!prev) return [agent]
      const idx = prev.findIndex((a) => a.id === agent.id)
      if (idx >= 0) {
        const next = [...prev]
        next[idx] = agent
        // Update the detail drawer if this agent is open
        if (detailAgent?.id === agent.id) setDetailAgent(agent)
        return next
      }
      return [agent, ...prev]
    })
  }

  function removeAgent(agentId: string) {
    queryClient.setQueryData<AgentOut[]>(['agents'], (prev) =>
      (prev ?? []).filter((a) => a.id !== agentId),
    )
    if (detailAgent?.id === agentId) setDetailAgent(null)
  }

  // ── Action handlers ───────────────────────────────────────────────────────

  function handleEdit(agent: AgentOut) {
    setEditingAgent(agent)
    setShowBuilder(true)
    setDetailAgent(null)
  }

  async function handleDelete(agent: AgentOut) {
    if (!confirm(`Delete "${agent.name}"? This cannot be undone.`)) return
    try {
      await agentApi.delete(agent.id)
      removeAgent(agent.id)
      toast.success(`"${agent.name}" deleted.`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Delete failed.')
    }
  }

  async function handleStatusChange(agent: AgentOut, newStatus: AgentStatus) {
    try {
      const updated = await agentApi.updateStatus(agent.id, newStatus)
      upsertAgent(updated)
      const msg: Partial<Record<AgentStatus, string>> = {
        live: `"${updated.name}" is now Live — triggers enabled.`,
        paused: `"${updated.name}" paused — triggers halted.`,
      }
      toast.success(msg[newStatus] ?? `Moved to ${newStatus}.`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Status update failed.')
    }
  }

  function handleCloseBuilder() {
    setShowBuilder(false)
    setEditingAgent(undefined)
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col h-full">
      {/* Page header */}
      <div className="flex-shrink-0 border-b border-gray-800 bg-gray-950 px-6 py-4">
        <div className="max-w-screen-2xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-white">Agent Board</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              {agents.length} agent{agents.length !== 1 ? 's' : ''} ·{' '}
              {agents.filter((a) => a.status === 'live').length} live
            </p>
          </div>

          <div className="flex items-center gap-2">
            {/* View toggle */}
            <div className="flex items-center bg-gray-900 border border-gray-800 rounded-lg p-0.5">
              <button
                onClick={() => setViewMode('kanban')}
                className={cn(
                  'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors',
                  viewMode === 'kanban'
                    ? 'bg-gray-700 text-white'
                    : 'text-gray-500 hover:text-gray-300',
                )}
                aria-pressed={viewMode === 'kanban'}
              >
                <LayoutGrid size={13} aria-hidden="true" /> Board
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={cn(
                  'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors',
                  viewMode === 'list'
                    ? 'bg-gray-700 text-white'
                    : 'text-gray-500 hover:text-gray-300',
                )}
                aria-pressed={viewMode === 'list'}
              >
                <List size={13} aria-hidden="true" /> List
              </button>
            </div>

            <Button onClick={() => { setEditingAgent(undefined); setShowBuilder(true) }}>
              <Plus size={14} aria-hidden="true" />
              New agent
            </Button>
          </div>
        </div>
      </div>

      {/* Board content */}
      <div className="flex-1 overflow-hidden">
        {agentsLoading && (
          <div className="flex items-center justify-center h-full text-gray-600">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-700 border-t-forge-500 mr-3" />
            Loading agents…
          </div>
        )}

        {!agentsLoading && viewMode === 'kanban' && (
          <div className="h-full overflow-x-auto px-6 py-5">
            <KanbanBoard
              agents={agents}
              lastRunByAgent={lastRunByAgent}
              voiceAgentsByAgentId={voiceAgentsByAgentId}
              onAgentsChange={setAgents}
              onOpenDetail={setDetailAgent}
            />
          </div>
        )}

        {!agentsLoading && viewMode === 'list' && (
          <div className="max-w-6xl mx-auto px-6 py-6">
            {agents.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 text-center gap-4">
                <p className="text-gray-500">No agents yet.</p>
                <Button onClick={() => setShowBuilder(true)}>
                  <Plus size={14} />
                  Build your first agent
                </Button>
              </div>
            ) : (
              <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
                <table className="w-full text-left">
                  <thead>
                    <tr className="border-b border-gray-800">
                      {['Agent', 'Status', 'Trigger', 'Connectors', 'Runs', 'Cost', ''].map((h) => (
                        <th
                          key={h}
                          className={`px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider${
                            h === 'Runs' || h === 'Cost' ? ' text-right' : ''
                          }`}
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {agents.map((agent) => (
                      <AgentRow
                        key={agent.id}
                        agent={agent}
                        onEdit={handleEdit}
                        onDelete={handleDelete}
                        onUpdated={upsertAgent}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Detail drawer */}
      {detailAgent && (
        <AgentDetailDrawer
          agent={detailAgent}
          onClose={() => setDetailAgent(null)}
          onEdit={handleEdit}
          onDelete={handleDelete}
          onStatusChange={handleStatusChange}
          onAgentUpdated={upsertAgent}
        />
      )}

      {/* Builder modal */}
      {showBuilder && (
        <AgentBuilderModal
          connectors={connectors}
          onClose={handleCloseBuilder}
          onCreated={upsertAgent}
          editAgent={editingAgent}
        />
      )}
    </div>
  )
}
