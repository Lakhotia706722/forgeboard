import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { GripVertical, Phone, AlertTriangle, Clock, TrendingUp } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { cn } from '@/lib/utils'
import type { AgentOut } from '@/lib/agentApi'
import type { VoiceAgentOut } from '@/lib/voiceApi'
import { voiceApi, formatDuration } from '@/lib/voiceApi'
import CallStatusBadge from './CallStatusBadge'

interface VoiceAgentCardProps {
  agent: AgentOut
  voiceAgent: VoiceAgentOut
  onOpenDetail: (agent: AgentOut) => void
  isDragging?: boolean
}

/** Average call duration in seconds, guarded against zero-call case. */
function avgDuration(va: VoiceAgentOut): number {
  if (va.total_calls === 0) return 0
  return Math.round(va.total_call_seconds / va.total_calls)
}

/** Escalation rate as a percentage string, or "—" if no calls. */
function escalationRate(va: VoiceAgentOut): string {
  if (va.total_calls === 0) return '—'
  const pct = Math.round((va.total_escalations / va.total_calls) * 100)
  return `${pct}%`
}

export default function VoiceAgentCard({
  agent,
  voiceAgent,
  onOpenDetail,
  isDragging = false,
}: VoiceAgentCardProps) {
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

  // Poll for live calls only when the agent is in the "live" lane.
  // 5-second interval per the locked decision in Phase 8 design.
  const { data: liveCalls = [] } = useQuery({
    queryKey: ['calls-live', voiceAgent.id],
    queryFn: () => voiceApi.listAgentCalls(voiceAgent.id, 10),
    refetchInterval: agent.status === 'live' ? 5000 : false,
    enabled: agent.status === 'live',
  })

  const activeCall = liveCalls.find(
    (c) => c.status === 'in_progress' || c.status === 'ringing',
  )

  const hasHighEscalation =
    voiceAgent.total_calls > 0 &&
    voiceAgent.total_escalations / voiceAgent.total_calls > 0.2 // >20% triggers warning

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
      {/* Top row: drag handle + name + alerts */}
      <div className="flex items-start gap-2">
        {/* Drag handle */}
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
          <div className="flex items-center gap-1.5">
            {/* Voice indicator */}
            <Phone
              size={11}
              className="flex-shrink-0 text-forge-400"
              aria-label="Voice agent"
            />
            <p className="text-sm font-medium text-white truncate leading-tight">
              {agent.name}
            </p>
          </div>
          <p className="text-xs text-gray-500 mt-0.5 line-clamp-2 leading-snug">
            {agent.goal}
          </p>
        </div>

        {/* Alerts */}
        <div className="flex flex-col gap-1 flex-shrink-0 mt-0.5">
          {agent.consecutive_failures >= 3 && (
            <AlertTriangle
              size={13}
              className="text-red-400"
              aria-label="Multiple consecutive failures"
            />
          )}
          {hasHighEscalation && (
            <TrendingUp
              size={13}
              className="text-amber-400"
              aria-label="High escalation rate"
            />
          )}
        </div>
      </div>

      {/* Live call badge — shown only when a call is active */}
      {activeCall && (
        <div className="mt-2">
          <CallStatusBadge status={activeCall.status} />
        </div>
      )}

      {/* Phone number */}
      {voiceAgent.phone_number && (
        <p className="mt-1.5 text-xs font-mono text-gray-600 truncate">
          {voiceAgent.phone_number}
        </p>
      )}

      {/* Bottom row: metrics */}
      <div className="flex items-center gap-3 mt-3 pt-2.5 border-t border-gray-800">
        {/* Call volume */}
        <span
          className="flex items-center gap-1 text-xs text-gray-600"
          title="Total calls"
        >
          <Phone size={10} aria-hidden="true" />
          {voiceAgent.total_calls} calls
        </span>

        {/* Avg duration */}
        <span
          className="flex items-center gap-1 text-xs text-gray-600"
          title="Average call duration"
        >
          <Clock size={10} aria-hidden="true" />
          {formatDuration(avgDuration(voiceAgent))}
        </span>

        <span className="flex-1" />

        {/* Escalation rate — amber when non-zero, red when high */}
        <span
          className={cn(
            'text-xs font-medium',
            voiceAgent.total_escalations === 0
              ? 'text-gray-700'
              : hasHighEscalation
              ? 'text-red-400'
              : 'text-amber-400',
          )}
          title={`${voiceAgent.total_escalations} escalation${voiceAgent.total_escalations !== 1 ? 's' : ''} of ${voiceAgent.total_calls} calls`}
          aria-label={`Escalation rate: ${escalationRate(voiceAgent)}`}
        >
          {escalationRate(voiceAgent)} esc
        </span>
      </div>
    </div>
  )
}
