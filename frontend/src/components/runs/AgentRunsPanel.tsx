import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Play, ChevronRight } from 'lucide-react'
import toast from 'react-hot-toast'

import { runApi, type RunOut } from '@/lib/runApi'
import { agentApi, type AgentOut } from '@/lib/agentApi'
import Button from '@/components/ui/Button'
import RunStatusBadge from './RunStatusBadge'
import RunDetailModal from './RunDetailModal'

interface AgentRunsPanelProps {
  agent: AgentOut
  onAgentUpdated: (agent: AgentOut) => void
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function costDisplay(cents: number) {
  if (cents === 0) return '—'
  return `$${(cents / 100).toFixed(4)}`
}

export default function AgentRunsPanel({ agent, onAgentUpdated }: AgentRunsPanelProps) {
  const queryClient = useQueryClient()
  const [triggering, setTriggering] = useState(false)
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)

  const { data: runs = [], isLoading } = useQuery({
    queryKey: ['runs', agent.id],
    queryFn: () => runApi.listForAgent(agent.id),
    // Poll while any run is active
    refetchInterval: (query) => {
      const hasActive = query.state.data?.some(
        (r) => r.status === 'pending' || r.status === 'running',
      )
      return hasActive ? 3000 : false
    },
  })

  async function handleRunNow() {
    setTriggering(true)
    try {
      const run = await runApi.trigger(agent.id)
      // Optimistically add to run list
      queryClient.setQueryData<RunOut[]>(['runs', agent.id], (prev) => [
        run,
        ...(prev ?? []),
      ])
      toast.success('Run started.')

      // Refresh agent to get updated counters
      const updated = await agentApi.get(agent.id)
      onAgentUpdated(updated)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to start run.')
    } finally {
      setTriggering(false)
    }
  }

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-400">
          {runs.length} run{runs.length !== 1 ? 's' : ''}
        </p>
        <Button size="sm" loading={triggering} onClick={handleRunNow}>
          <Play size={13} aria-hidden="true" />
          Run now
        </Button>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center justify-center py-8 text-gray-600">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-gray-700 border-t-forge-500 mr-2" />
          Loading runs…
        </div>
      )}

      {/* Empty */}
      {!isLoading && runs.length === 0 && (
        <div className="text-center py-8 text-sm text-gray-600">
          No runs yet. Hit "Run now" to execute this agent.
        </div>
      )}

      {/* Run list */}
      {!isLoading && runs.length > 0 && (
        <div className="divide-y divide-gray-800 rounded-xl border border-gray-800 overflow-hidden">
          {runs.map((run) => (
            <button
              key={run.id}
              onClick={() => setSelectedRunId(run.id)}
              className="w-full flex items-center gap-4 px-4 py-3 bg-gray-900 hover:bg-gray-800/80 transition-colors text-left"
            >
              <RunStatusBadge status={run.status} />

              <div className="flex-1 min-w-0">
                <p className="text-xs text-gray-400">{formatDate(run.created_at)}</p>
                {run.output && (
                  <p className="text-xs text-gray-500 truncate mt-0.5">{run.output}</p>
                )}
                {run.error && (
                  <p className="text-xs text-red-500 truncate mt-0.5">{run.error}</p>
                )}
              </div>

              <div className="flex items-center gap-4 flex-shrink-0">
                <span className="text-xs text-gray-600">
                  {run.input_tokens + run.output_tokens > 0
                    ? `${run.input_tokens + run.output_tokens} tok`
                    : ''}
                </span>
                <span className="text-xs text-gray-600">{costDisplay(run.cost_usd_cents)}</span>
                <ChevronRight size={14} className="text-gray-600" />
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Run detail modal */}
      {selectedRunId && (
        <RunDetailModal
          runId={selectedRunId}
          agentName={agent.name}
          onClose={() => setSelectedRunId(null)}
        />
      )}
    </div>
  )
}
