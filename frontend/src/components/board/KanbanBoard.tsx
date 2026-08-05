import { useState, useCallback } from 'react'
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  type DragStartEvent,
  type DragEndEvent,
  type DragOverEvent,
} from '@dnd-kit/core'
import toast from 'react-hot-toast'

import { agentApi, type AgentOut, type AgentStatus } from '@/lib/agentApi'
import type { RunOut } from '@/lib/runApi'
import type { VoiceAgentOut } from '@/lib/voiceApi'
import { LANES } from './boardConfig'
import KanbanLane from './KanbanLane'
import AgentCard from './AgentCard'
import VoiceAgentCard from '@/components/voice/VoiceAgentCard'

interface KanbanBoardProps {
  agents: AgentOut[]
  lastRunByAgent: Record<string, RunOut>
  voiceAgentsByAgentId: Record<string, VoiceAgentOut>
  onAgentsChange: (agents: AgentOut[]) => void
  onOpenDetail: (agent: AgentOut) => void
}

export default function KanbanBoard({
  agents,
  lastRunByAgent,
  voiceAgentsByAgentId,
  onAgentsChange,
  onOpenDetail,
}: KanbanBoardProps) {
  const [activeAgent, setActiveAgent] = useState<AgentOut | null>(null)
  const [overLaneId, setOverLaneId] = useState<AgentStatus | null>(null)

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 8 }, // require 8px of movement before drag starts
    }),
  )

  // Group agents by status for each lane
  const agentsByLane = Object.fromEntries(
    LANES.map((lane) => [lane.id, agents.filter((a) => a.status === lane.id)]),
  ) as Record<AgentStatus, AgentOut[]>

  function handleDragStart({ active }: DragStartEvent) {
    const agent = agents.find((a) => a.id === active.id)
    if (agent) setActiveAgent(agent)
  }

  function handleDragOver({ over }: DragOverEvent) {
    if (!over) {
      setOverLaneId(null)
      return
    }
    // over.id is either a lane id or another agent id
    const laneIds = LANES.map((l) => l.id as string)
    if (laneIds.includes(over.id as string)) {
      setOverLaneId(over.id as AgentStatus)
    } else {
      // Find which lane the hovered agent belongs to
      const hoveredAgent = agents.find((a) => a.id === over.id)
      if (hoveredAgent) setOverLaneId(hoveredAgent.status)
    }
  }

  const handleDragEnd = useCallback(
    async ({ over }: DragEndEvent) => {
      setActiveAgent(null)
      setOverLaneId(null)

      if (!over || !activeAgent) return

      const laneIds = LANES.map((l) => l.id as string)
      let targetLane: AgentStatus

      if (laneIds.includes(over.id as string)) {
        targetLane = over.id as AgentStatus
      } else {
        const hoveredAgent = agents.find((a) => a.id === over.id)
        if (!hoveredAgent) return
        targetLane = hoveredAgent.status
      }

      if (targetLane === activeAgent.status) return

      // Optimistic update
      const optimistic = agents.map((a) =>
        a.id === activeAgent.id ? { ...a, status: targetLane } : a,
      )
      onAgentsChange(optimistic)

      try {
        const updated = await agentApi.updateStatus(activeAgent.id, targetLane)
        // Merge the real updated agent in
        onAgentsChange(
          optimistic.map((a) => (a.id === updated.id ? updated : a)),
        )

        const messages: Partial<Record<AgentStatus, string>> = {
          live: `"${updated.name}" is now Live — triggers enabled.`,
          paused: `"${updated.name}" paused — triggers halted.`,
          needs_review: `"${updated.name}" moved to Needs Review.`,
        }
        toast.success(messages[targetLane] ?? `Moved to ${targetLane}.`)
      } catch (err) {
        // Roll back optimistic update
        onAgentsChange(agents)
        toast.error(err instanceof Error ? err.message : 'Move failed.')
      }
    },
    [activeAgent, agents, onAgentsChange],
  )

  return (
    <DndContext
      sensors={sensors}
      onDragStart={handleDragStart}
      onDragOver={handleDragOver}
      onDragEnd={handleDragEnd}
    >
      {/* Board scroll container */}
      <div className="flex gap-3 overflow-x-auto pb-4 min-h-[60vh]">
        {LANES.map((lane) => (
          <KanbanLane
            key={lane.id}
            lane={lane}
            agents={agentsByLane[lane.id] ?? []}
            lastRunByAgent={lastRunByAgent}
            voiceAgentsByAgentId={voiceAgentsByAgentId}
            onOpenDetail={onOpenDetail}
            isOver={overLaneId === lane.id}
          />
        ))}
      </div>

      {/* Drag overlay — floating ghost card */}
      <DragOverlay>
        {activeAgent && (
          voiceAgentsByAgentId[activeAgent.id] ? (
            <VoiceAgentCard
              agent={activeAgent}
              voiceAgent={voiceAgentsByAgentId[activeAgent.id]}
              onOpenDetail={() => {}}
              isDragging
            />
          ) : (
            <AgentCard
              agent={activeAgent}
              lastRun={lastRunByAgent[activeAgent.id]}
              onOpenDetail={() => {}}
              isDragging
            />
          )
        )}
      </DragOverlay>
    </DndContext>
  )
}
