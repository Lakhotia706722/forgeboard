import { useDroppable } from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { cn } from '@/lib/utils'
import type { AgentOut } from '@/lib/agentApi'
import type { RunOut } from '@/lib/runApi'
import type { LaneConfig } from './boardConfig'
import AgentCard from './AgentCard'

interface KanbanLaneProps {
  lane: LaneConfig
  agents: AgentOut[]
  lastRunByAgent: Record<string, RunOut>
  onOpenDetail: (agent: AgentOut) => void
  isOver: boolean
}

export default function KanbanLane({
  lane,
  agents,
  lastRunByAgent,
  onOpenDetail,
  isOver,
}: KanbanLaneProps) {
  const { setNodeRef } = useDroppable({ id: lane.id })

  return (
    <div className="flex flex-col min-w-[240px] w-60 flex-shrink-0">
      {/* Lane header */}
      <div
        className={cn(
          'rounded-t-xl px-3 py-2.5 border border-b-0 border-gray-800',
          lane.headerBg,
        )}
      >
        <div className="flex items-center justify-between">
          <h3 className={cn('text-xs font-semibold uppercase tracking-wider', lane.color)}>
            {lane.label}
          </h3>
          <span className="text-xs text-gray-600 font-medium tabular-nums">
            {agents.length}
          </span>
        </div>
        <p className="text-xs text-gray-600 mt-0.5 leading-snug">{lane.description}</p>
      </div>

      {/* Drop zone */}
      <div
        ref={setNodeRef}
        className={cn(
          'flex-1 min-h-[120px] rounded-b-xl border border-gray-800 p-2 space-y-2',
          'transition-colors duration-150',
          isOver ? 'bg-forge-900/20 border-forge-700' : 'bg-gray-900/30',
        )}
      >
        <SortableContext
          items={agents.map((a) => a.id)}
          strategy={verticalListSortingStrategy}
        >
          {agents.map((agent) => (
            <AgentCard
              key={agent.id}
              agent={agent}
              lastRun={lastRunByAgent[agent.id]}
              onOpenDetail={onOpenDetail}
            />
          ))}
        </SortableContext>

        {agents.length === 0 && (
          <div
            className={cn(
              'flex items-center justify-center h-16 rounded-lg border border-dashed',
              isOver ? 'border-forge-600 text-forge-500' : 'border-gray-800 text-gray-700',
              'text-xs transition-colors duration-150',
            )}
          >
            {isOver ? 'Drop here' : 'Empty'}
          </div>
        )}
      </div>
    </div>
  )
}
