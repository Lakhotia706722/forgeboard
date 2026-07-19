import { cn } from '@/lib/utils'
import type { RunStatus } from '@/lib/runApi'

const STYLES: Record<RunStatus, { dot: string; label: string; bg: string }> = {
  pending:   { dot: 'bg-gray-400',   label: 'Pending',   bg: 'bg-gray-800 text-gray-400' },
  running:   { dot: 'bg-blue-400 animate-pulse', label: 'Running', bg: 'bg-blue-900/40 text-blue-300' },
  success:   { dot: 'bg-green-400',  label: 'Success',   bg: 'bg-green-900/40 text-green-300' },
  failed:    { dot: 'bg-red-400',    label: 'Failed',    bg: 'bg-red-900/40 text-red-300' },
  cancelled: { dot: 'bg-yellow-400', label: 'Cancelled', bg: 'bg-yellow-900/40 text-yellow-300' },
}

export default function RunStatusBadge({ status }: { status: RunStatus }) {
  const s = STYLES[status]
  return (
    <span className={cn('inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium', s.bg)}>
      <span className={cn('h-1.5 w-1.5 rounded-full', s.dot)} aria-hidden="true" />
      {s.label}
    </span>
  )
}
