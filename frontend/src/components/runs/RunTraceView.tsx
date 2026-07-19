import { cn } from '@/lib/utils'
import type { TraceEvent } from '@/lib/runApi'

const EVENT_STYLES: Record<string, { label: string; color: string; bg: string }> = {
  llm_call:    { label: 'LLM',    color: 'text-purple-300', bg: 'bg-purple-900/30 border-purple-800' },
  tool_call:   { label: 'TOOL →', color: 'text-blue-300',   bg: 'bg-blue-900/30 border-blue-800' },
  tool_result: { label: '← RESULT', color: 'text-teal-300', bg: 'bg-teal-900/30 border-teal-800' },
  error:       { label: 'ERROR',  color: 'text-red-300',    bg: 'bg-red-900/30 border-red-800' },
  output:      { label: 'OUTPUT', color: 'text-green-300',  bg: 'bg-green-900/30 border-green-800' },
  system:      { label: 'SYS',    color: 'text-yellow-300', bg: 'bg-yellow-900/30 border-yellow-800' },
}

function formatTs(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return iso
  }
}

function DataBlock({ data }: { data: Record<string, unknown> }) {
  return (
    <pre className="mt-1.5 text-xs text-gray-300 bg-gray-950 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap break-words">
      {JSON.stringify(data, null, 2)}
    </pre>
  )
}

interface RunTraceViewProps {
  trace: TraceEvent[]
}

export default function RunTraceView({ trace }: RunTraceViewProps) {
  if (trace.length === 0) {
    return <p className="text-sm text-gray-600 py-4 text-center">No trace events.</p>
  }

  return (
    <div className="space-y-2">
      {trace.map((event) => {
        const style = EVENT_STYLES[event.type] ?? {
          label: event.type.toUpperCase(),
          color: 'text-gray-300',
          bg: 'bg-gray-800 border-gray-700',
        }

        return (
          <div
            key={event.seq}
            className={cn('rounded-lg border px-3 py-2.5', style.bg)}
          >
            <div className="flex items-center gap-2 mb-1">
              <span className={cn('text-xs font-mono font-semibold', style.color)}>
                {style.label}
              </span>
              <span className="text-xs text-gray-600 font-mono">
                #{event.seq} · {formatTs(event.timestamp)}
              </span>
            </div>
            {/* Show key fields in the data object cleanly */}
            {event.type === 'tool_call' && (
              <p className="text-xs text-gray-300">
                <span className="text-blue-400 font-medium">{String(event.data.tool)}</span>
              </p>
            )}
            {event.type === 'tool_result' && (
              <p className="text-xs text-gray-300">
                <span className="text-teal-400 font-medium">{String(event.data.tool)}</span>
              </p>
            )}
            {event.type === 'system' && (
              <p className="text-xs text-yellow-300">{String(event.data.message ?? '')}</p>
            )}
            <DataBlock data={event.data} />
          </div>
        )
      })}
    </div>
  )
}
