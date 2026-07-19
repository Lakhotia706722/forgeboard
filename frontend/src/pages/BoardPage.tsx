import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Cpu } from 'lucide-react'
import toast from 'react-hot-toast'

import { agentApi, type AgentOut } from '@/lib/agentApi'
import { connectorApi } from '@/lib/connectorApi'
import Button from '@/components/ui/Button'
import AgentRow from '@/components/agents/AgentRow'
import AgentBuilderModal from '@/components/agents/AgentBuilderModal'

export default function BoardPage() {
  const queryClient = useQueryClient()
  const [showBuilder, setShowBuilder] = useState(false)
  const [editingAgent, setEditingAgent] = useState<AgentOut | undefined>(undefined)

  const { data: agents = [], isLoading: agentsLoading } = useQuery({
    queryKey: ['agents'],
    queryFn: agentApi.list,
  })

  const { data: connectors = [] } = useQuery({
    queryKey: ['connectors'],
    queryFn: connectorApi.list,
  })

  function handleCreated(agent: AgentOut) {
    queryClient.setQueryData<AgentOut[]>(['agents'], (prev) => {
      if (!prev) return [agent]
      const idx = prev.findIndex((a) => a.id === agent.id)
      if (idx >= 0) {
        const next = [...prev]
        next[idx] = agent
        return next
      }
      return [agent, ...prev]
    })
  }

  function handleEdit(agent: AgentOut) {
    setEditingAgent(agent)
    setShowBuilder(true)
  }

  async function handleDelete(agent: AgentOut) {
    if (!confirm(`Delete "${agent.name}"? This cannot be undone.`)) return
    try {
      await agentApi.delete(agent.id)
      queryClient.setQueryData<AgentOut[]>(['agents'], (prev) =>
        (prev ?? []).filter((a) => a.id !== agent.id),
      )
      toast.success(`"${agent.name}" deleted.`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Delete failed.')
    }
  }

  function handleCloseBuilder() {
    setShowBuilder(false)
    setEditingAgent(undefined)
  }

  return (
    <div className="max-w-6xl mx-auto px-6 py-10">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Agents</h1>
          <p className="mt-1 text-sm text-gray-400">
            Build, configure, and deploy your AI agents.
            {' '}
            <span className="text-gray-600">Kanban view coming in Phase 5.</span>
          </p>
        </div>
        <Button onClick={() => { setEditingAgent(undefined); setShowBuilder(true) }}>
          <Plus size={15} aria-hidden="true" />
          New agent
        </Button>
      </div>

      {/* Loading */}
      {agentsLoading && (
        <div className="flex items-center justify-center py-20 text-gray-600">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-700 border-t-forge-500 mr-3" />
          Loading agents…
        </div>
      )}

      {/* Empty */}
      {!agentsLoading && agents.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center gap-4">
          <div className="p-4 rounded-2xl bg-gray-900 border border-gray-800">
            <Cpu size={28} className="text-gray-600" />
          </div>
          <div>
            <p className="font-medium text-gray-300">No agents yet</p>
            <p className="text-sm text-gray-600 mt-1">
              Describe a goal, pick some connectors, and deploy your first agent.
            </p>
          </div>
          <Button onClick={() => setShowBuilder(true)}>
            <Plus size={15} />
            Build your first agent
          </Button>
        </div>
      )}

      {/* Agent table */}
      {!agentsLoading && agents.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-gray-800 bg-gray-900/80">
                <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Agent
                </th>
                <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Trigger
                </th>
                <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Connectors
                </th>
                <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-right">
                  Runs
                </th>
                <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-right">
                  Cost
                </th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {agents.map((agent) => (
                <AgentRow
                  key={agent.id}
                  agent={agent}
                  onEdit={handleEdit}
                  onDelete={handleDelete}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Builder modal */}
      {showBuilder && (
        <AgentBuilderModal
          connectors={connectors}
          onClose={handleCloseBuilder}
          onCreated={handleCreated}
          editAgent={editingAgent}
        />
      )}
    </div>
  )
}
