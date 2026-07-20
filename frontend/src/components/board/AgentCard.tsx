import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { GripVertical, Zap, AlertTriangle, Play, Pencil } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { AgentOut } from '@/lib/agentApi'
import type { RunOut } from '@/lib/runApi'

const TRIGGER_ICON: Record<string, React.ElementType> = {
  manual: Play,
  scheduled: Zap,
  webhook: Zap,
}

interface AgentCardProps {
  agent: AgentOut
  lastRun?: RunOut
  onOpenDetail: (agent: AgentOut) => void
  isDragging?: boolean
}

const RUN_STATUS_DOT: Record<string, string> = {
  success:  'bg-green-400',
  failed:   'bg-red-400',
  running:  'bg-blue-400 animate-pulse',
  pending:  'bg-gray-500',
  cancelled:'bg-yellow-400',
}

export default function AgentCard({
  agent,
  lastRun,
  onOpenDetail,
  isDragging = false,
}: AgentCardProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging: isSortableDragging,
  } = useSortable({ id: agent.id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }

  const TriggerIcon = TRIGGER_ICON[agent.trigger_type] ?? Play
  const costDisplay =
    agent.total_cost_usd_cents > 0
      ? `$${(agent.total_cost_usd_cents / 100).toFixed(2)}`
      : null

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        'group bg-gray-900 border border-gray-800 rounded-xl p-3.5',
        'hover:border-gray-700 transition-colors cursor-pointer',
        (isDragging || isSortableDragging) && 'opacity-50 shadow-2xl ring-2 ring-forge-500',
      )}
      onClick={() => onOpenDetail(agent)}
    >
      {/* Top row: drag handle + name + alert */}
      <div className="flex items-start gap-2">
        {/* Drag handle — separate from click */}
        <button
          {...attributes}
          {...listeners}
          onClick={(e) => e.stopPropagation()}
          className="mt-0.5 flex-shrink-0 text-gray-700 hover:text-gray-400 cursor-grab active:cursor-grabbing touch-none"
          aria-label="Drag to reorder"
        >
          <GripVertical size={14} aria-hidden="true" />
        </button>

        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-white truncate leading-tight">
            {agent.name}
          </p>
          <p className="text-xs text-gray-500 mt-0.5 line-clamp-2 leading-snug">
            {agent.goal}
          </p>
        </div>

        {agent.consecutive_failures >= 3 && (
          <AlertTriangle
            size={14}
            className="flex-shrink-0 text-red-400 mt-0.5"
            aria-label="Multiple consecutive failures"
          />
        )}
      </div>

      {/* Bottom row: meta info */}
      <div className="flex items-center gap-3 mt-3 pt-2.5 border-t border-gray-800">
        {/* Trigger */}
        <span className="flex items-center gap-1 text-xs text-gray-600">
          <TriggerIcon size={11} aria-hidden="true" />
          {agent.trigger_type}
        </span>

        {/* Last run status */}
        {lastRun && (
          <span className="flex items-center gap-1 text-xs text-gray-600">
            <span
              className={cn('h-1.5 w-1.5 rounded-full', RUN_STATUS_DOT[lastRun.status] ?? 'bg-gray-500')}
              aria-hidden="true"
            />
            {lastRun.status}
          </span>
        )}

        <span className="flex-1" />

        {/* Run count */}
        <span className="text-xs text-gray-700">{agent.total_runs} runs</span>

        {/* Cost */}
        {costDisplay && (
          <span className="text-xs text-gray-700">{costDisplay}</span>
        )}

        {/* Edit shortcut */}
        <button
          onClick={(e) => {
            e.stopPropagation()
            onOpenDetail(agent)
          }}
          className="opacity-0 group-hover:opacity-100 text-gray-600 hover:text-gray-300 transition-opacity"
          aria-label={`Open ${agent.name} detail`}
        >
          <Pencil size={11} aria-hidden="true" />
        </button>
      </div>
    </div>
  )
}
