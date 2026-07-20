import type { AgentStatus } from '@/lib/agentApi'

export interface LaneConfig {
  id: AgentStatus
  label: string
  description: string
  color: string          // Tailwind border/text color token
  headerBg: string       // header background
  cardBg: string         // card background
  allowDrop: boolean     // whether agents can be dragged into this lane
}

export const LANES: LaneConfig[] = [
  {
    id: 'draft',
    label: 'Draft',
    description: 'Being built — not yet runnable.',
    color: 'text-gray-400',
    headerBg: 'bg-gray-800/60',
    cardBg: 'bg-gray-900',
    allowDrop: true,
  },
  {
    id: 'testing',
    label: 'Testing',
    description: 'Run manually to validate behaviour.',
    color: 'text-blue-400',
    headerBg: 'bg-blue-900/30',
    cardBg: 'bg-gray-900',
    allowDrop: true,
  },
  {
    id: 'live',
    label: 'Live',
    description: 'Scheduled & webhook triggers active.',
    color: 'text-green-400',
    headerBg: 'bg-green-900/30',
    cardBg: 'bg-gray-900',
    allowDrop: true,
  },
  {
    id: 'paused',
    label: 'Paused',
    description: 'All triggers halted.',
    color: 'text-yellow-400',
    headerBg: 'bg-yellow-900/20',
    cardBg: 'bg-gray-900',
    allowDrop: true,
  },
  {
    id: 'needs_review',
    label: 'Needs Review',
    description: 'Auto-moved after 3 consecutive failures.',
    color: 'text-red-400',
    headerBg: 'bg-red-900/20',
    cardBg: 'bg-gray-900',
    allowDrop: true,
  },
]

export const LANE_MAP = Object.fromEntries(LANES.map((l) => [l.id, l])) as Record<
  AgentStatus,
  LaneConfig
>
