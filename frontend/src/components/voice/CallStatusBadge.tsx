import { cn } from '@/lib/utils'
import type { CallStatus } from '@/lib/voiceApi'

const STYLES: Record<CallStatus, { dot: string; label: string; bg: string }> = {
  idle:        { dot: 'bg-gray-500',               label: 'Idle',        bg: 'bg-gray-800 text-gray-400' },
  ringing:     { dot: 'bg-yellow-400 animate-pulse', label: 'Ringing',   bg: 'bg-yellow-900/40 text-yellow-300' },
  in_progress: { dot: 'bg-green-400 animate-pulse',  label: 'Live',      bg: 'bg-green-900/40 text-green-300' },
  completed:   { dot: 'bg-blue-400',                label: 'Completed',  bg: 'bg-blue-900/40 text-blue-300' },
  failed:      { dot: 'bg-red-400',                 label: 'Failed',     bg: 'bg-red-900/40 text-red-300' },
  transferred: { dot: 'bg-purple-400',              label: 'Transferred',bg: 'bg-purple-900/40 text-purple-300' },
}

export default function CallStatusBadge({ status }: { status: CallStatus }) {
  const s = STYLES[status]
  return (
    <span className={cn('inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium', s.bg)}>
      <span className={cn('h-1.5 w-1.5 rounded-full flex-shrink-0', s.dot)} aria-hidden="true" />
      {s.label}
    </span>
  )
}
