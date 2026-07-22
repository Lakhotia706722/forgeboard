import { useState } from 'react'
import { X, Pencil, Trash2, ChevronDown, ChevronUp } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { AgentOut, AgentStatus } from '@/lib/agentApi'
import { LANE_MAP } from './boardConfig'
import Button from '@/components/ui/Button'
import AgentRunsPanel from '@/components/runs/AgentRunsPanel'

interface AgentDetailDrawerProps {
  agent: AgentOut
  onClose: () => void
  onEdit: (agent: AgentOut) => void
  onDelete: (agent: AgentOut) => void
  onStatusChange: (agent: AgentOut, status: AgentStatus) => void
  onAgentUpdated: (agent: AgentOut) => void
}

// Allowed transitions (mirrors backend) so UI only shows valid moves
const ALLOWED: Record<AgentStatus, AgentStatus[]> = {
  draft:        ['testing', 'paused'],
  testing:      ['live', 'draft', 'paused'],
  live:         ['paused', 'needs_review'],
  paused:       ['draft', 'testing', 'live'],
  needs_review: ['paused', 'testing', 'live'],
}

export default function AgentDetailDrawer({
  agent,
  onClose,
  onEdit,
  onDelete,
  onStatusChange,
  onAgentUpdated,
}: AgentDetailDrawerProps) {
  const [showGoal, setShowGoal] = useState(false)
  const currentLane = LANE_MAP[agent.status]
  const allowedStatuses = ALLOWED[agent.status] ?? []

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer panel */}
      <aside
        className="relative z-50 w-full max-w-md bg-gray-900 border-l border-gray-800 flex flex-col h-full overflow-hidden shadow-2xl"
        aria-label={`${agent.name} detail`}
      >
        {/* Header */}
        <div className="flex items-start justify-between px-5 py-4 border-b border-gray-800 flex-shrink-0">
          <div className="flex-1 min-w-0 pr-4">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-0.5">Agent</p>
            <h2 className="font-semibold text-white text-lg leading-tight truncate">
              {agent.name}
            </h2>
            <span
              className={cn(
                'inline-block mt-1 text-xs font-medium px-2 py-0.5 rounded-full',
                currentLane.color,
                currentLane.headerBg,
              )}
            >
              {currentLane.label}
            </span>
          </div>
          <button
            onClick={onClose}
            className="flex-shrink-0 text-gray-500 hover:text-gray-200 transition-colors mt-0.5"
            aria-label="Close detail panel"
          >
            <X size={18} />
          </button>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto">
          {/* Stats */}
          <div className="grid grid-cols-3 gap-px bg-gray-800 border-b border-gray-800">
            {[
              { label: 'Total runs', value: agent.total_runs },
              {
                label: 'Cost',
                value:
                  agent.total_cost_usd_cents > 0
                    ? `$${(agent.total_cost_usd_cents / 100).toFixed(2)}`
                    : '$0.00',
              },
              { label: 'Failures', value: agent.consecutive_failures },
            ].map(({ label, value }) => (
              <div key={label} className="bg-gray-900 px-4 py-3 text-center">
                <p className="text-lg font-bold text-white">{value}</p>
                <p className="text-xs text-gray-500 mt-0.5">{label}</p>
              </div>
            ))}
          </div>

          <div className="px-5 py-4 space-y-5">
            {/* Goal — collapsible */}
            <div>
              <button
                onClick={() => setShowGoal((v) => !v)}
                className="flex items-center gap-1.5 text-xs font-semibold text-gray-500 uppercase tracking-wider hover:text-gray-300 transition-colors w-full text-left"
              >
                Goal
                {showGoal ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              </button>
              {showGoal && (
                <p className="mt-2 text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
                  {agent.goal}
                </p>
              )}
            </div>

            {/* Details */}
            <div className="space-y-2">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                Details
              </p>
              <dl className="space-y-1.5 text-sm">
                <div className="flex justify-between">
                  <dt className="text-gray-500">Trigger</dt>
                  <dd className="text-gray-300 capitalize">{agent.trigger_type}</dd>
                </div>
                {agent.cron_schedule && (
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Schedule</dt>
                    <dd className="text-gray-300 font-mono text-xs">{agent.cron_schedule}</dd>
                  </div>
                )}
                <div className="flex justify-between">
                  <dt className="text-gray-500">Approval gate</dt>
                  <dd className={agent.requires_approval ? 'text-yellow-400' : 'text-gray-600'}>
                    {agent.requires_approval ? 'Required' : 'Off'}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-500">Connectors</dt>
                  <dd className="text-gray-300 text-right">
                    {agent.connectors.length > 0
                      ? agent.connectors.map((c) => c.name).join(', ')
                      : '—'}
                  </dd>
                </div>
              </dl>
            </div>

            {/* Move to lane */}
            {allowedStatuses.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                  Move to
                </p>
                <div className="flex flex-wrap gap-2">
                  {allowedStatuses.map((s) => {
                    const lane = LANE_MAP[s]
                    return (
                      <button
                        key={s}
                        onClick={() => onStatusChange(agent, s)}
                        className={cn(
                          'px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors',
                          'border-gray-700 bg-gray-800 hover:border-gray-500 hover:bg-gray-700',
                          lane.color,
                        )}
                      >
                        {lane.label}
                        {s === 'live' && (
                          <span className="ml-1 text-gray-600">(enables triggers)</span>
                        )}
                        {s === 'paused' && (
                          <span className="ml-1 text-gray-600">(halts triggers)</span>
                        )}
                      </button>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Needs-review warning */}
            {agent.status === 'needs_review' && (
              <div className="rounded-xl bg-red-900/20 border border-red-800 px-4 py-3 text-sm text-red-300">
                <p className="font-semibold mb-1">⚠ Auto-flagged after {agent.consecutive_failures} consecutive failures</p>
                <p className="text-xs text-red-400">
                  Review the run history below, fix the issue, then move to Testing or Live.
                </p>
              </div>
            )}

            {/* Runs */}
            <div className="space-y-2">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                Run history
              </p>
              <AgentRunsPanel agent={agent} onAgentUpdated={onAgentUpdated} />
            </div>
          </div>
        </div>

        {/* Footer actions */}
        <div className="flex items-center gap-2 px-5 py-3 border-t border-gray-800 bg-gray-900 flex-shrink-0">
          <Button variant="secondary" size="sm" onClick={() => onEdit(agent)}>
            <Pencil size={13} />
            Edit
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onDelete(agent)}
            className="text-red-500 hover:text-red-400 ml-auto"
          >
            <Trash2 size={13} />
            Delete
          </Button>
        </div>
      </aside>
    </div>
  )
}
