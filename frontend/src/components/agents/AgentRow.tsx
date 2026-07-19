import { Pencil, Trash2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { AgentOut, AgentStatus } from '@/lib/agentApi'
import Button from '@/components/ui/Button'

const STATUS_STYLES: Record<AgentStatus, { dot: string; label: string; bg: string }> = {
  draft:        { dot: 'bg-gray-400',   label: 'Draft',        bg: 'bg-gray-800 text-gray-300' },
  testing:      { dot: 'bg-blue-400',   label: 'Testing',      bg: 'bg-blue-900/40 text-blue-300' },
  live:         { dot: 'bg-green-400',  label: 'Live',         bg: 'bg-green-900/40 text-green-300' },
  paused:       { dot: 'bg-yellow-400', label: 'Paused',       bg: 'bg-yellow-900/40 text-yellow-300' },
  needs_review: { dot: 'bg-red-400',    label: 'Needs Review', bg: 'bg-red-900/40 text-red-300' },
}

const TRIGGER_LABEL: Record<string, string> = {
  manual: 'Manual',
  scheduled: 'Scheduled',
  webhook: 'Webhook',
}

interface AgentRowProps {
  agent: AgentOut
  onEdit: (agent: AgentOut) => void
  onDelete: (agent: AgentOut) => void
}

export default function AgentRow({ agent, onEdit, onDelete }: AgentRowProps) {
  const s = STATUS_STYLES[agent.status]
  const costDisplay =
    agent.total_cost_usd_cents > 0
      ? `$${(agent.total_cost_usd_cents / 100).toFixed(2)}`
      : '—'

  return (
    <tr className="border-b border-gray-800 hover:bg-gray-900/50 transition-colors">
      <td className="px-4 py-3">
        <div>
          <p className="text-sm font-medium text-white">{agent.name}</p>
          <p className="text-xs text-gray-500 mt-0.5 line-clamp-1">{agent.goal}</p>
        </div>
      </td>

      <td className="px-4 py-3">
        <span
          className={cn(
            'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium',
            s.bg,
          )}
        >
          <span className={cn('h-1.5 w-1.5 rounded-full', s.dot)} aria-hidden="true" />
          {s.label}
        </span>
      </td>

      <td className="px-4 py-3 text-xs text-gray-400">
        {TRIGGER_LABEL[agent.trigger_type]}
        {agent.cron_schedule && (
          <span className="ml-1 font-mono text-gray-600">{agent.cron_schedule}</span>
        )}
      </td>

      <td className="px-4 py-3 text-xs text-gray-400">
        {agent.connectors.length > 0
          ? agent.connectors.map((c) => c.name).join(', ')
          : <span className="text-gray-700">None</span>}
      </td>

      <td className="px-4 py-3 text-xs text-gray-400 text-right">{agent.total_runs}</td>
      <td className="px-4 py-3 text-xs text-gray-400 text-right">{costDisplay}</td>

      <td className="px-4 py-3">
        <div className="flex items-center justify-end gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onEdit(agent)}
            aria-label={`Edit ${agent.name}`}
            className="text-gray-500 hover:text-gray-200 p-1.5"
          >
            <Pencil size={13} aria-hidden="true" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onDelete(agent)}
            aria-label={`Delete ${agent.name}`}
            className="text-gray-500 hover:text-red-400 p-1.5"
          >
            <Trash2 size={13} aria-hidden="true" />
          </Button>
        </div>
      </td>
    </tr>
  )
}
