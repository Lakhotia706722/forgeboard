import { useQuery } from '@tanstack/react-query'
import { X, Clock, Zap, DollarSign } from 'lucide-react'
import { runApi } from '@/lib/runApi'
import RunStatusBadge from './RunStatusBadge'
import RunTraceView from './RunTraceView'

interface RunDetailModalProps {
  runId: string
  agentName: string
  onClose: () => void
}

function duration(start: string | null, end: string | null): string {
  if (!start) return '—'
  const s = new Date(start).getTime()
  const e = end ? new Date(end).getTime() : Date.now()
  const ms = e - s
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`
}

export default function RunDetailModal({ runId, agentName, onClose }: RunDetailModalProps) {
  const { data: run, isLoading } = useQuery({
    queryKey: ['run', runId],
    queryFn: () => runApi.get(runId),
    // Poll every 2s while the run is active
    refetchInterval: (query) => {
      const s = query.state.data?.status
      return s === 'pending' || s === 'running' ? 2000 : false
    },
  })

  const costDisplay =
    run && run.cost_usd_cents > 0
      ? `$${(run.cost_usd_cents / 100).toFixed(4)}`
      : '$0.00'

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Run detail"
    >
      <div className="w-full max-w-3xl bg-gray-900 border border-gray-800 rounded-2xl shadow-2xl flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800 flex-shrink-0">
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-0.5">Run detail</p>
            <h2 className="font-semibold text-white">{agentName}</h2>
          </div>
          <div className="flex items-center gap-3">
            {run && <RunStatusBadge status={run.status} />}
            <button
              onClick={onClose}
              className="text-gray-500 hover:text-gray-300 transition-colors"
              aria-label="Close"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Loading */}
        {isLoading && (
          <div className="flex items-center justify-center py-16 text-gray-600">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-700 border-t-forge-500 mr-3" />
            Loading run…
          </div>
        )}

        {run && (
          <>
            {/* Stats bar */}
            <div className="flex items-center gap-6 px-6 py-3 border-b border-gray-800 bg-gray-900/60 flex-shrink-0">
              <div className="flex items-center gap-1.5 text-xs text-gray-400">
                <Clock size={12} aria-hidden="true" />
                {duration(run.started_at, run.finished_at)}
              </div>
              <div className="flex items-center gap-1.5 text-xs text-gray-400">
                <Zap size={12} aria-hidden="true" />
                {run.input_tokens + run.output_tokens} tokens
                <span className="text-gray-600">
                  ({run.input_tokens}↑ {run.output_tokens}↓)
                </span>
              </div>
              <div className="flex items-center gap-1.5 text-xs text-gray-400">
                <DollarSign size={12} aria-hidden="true" />
                {costDisplay}
              </div>
              <span className="text-xs text-gray-600 capitalize">
                via {run.trigger_source}
              </span>
            </div>

            {/* Body */}
            <div className="overflow-y-auto flex-1 p-6 space-y-5">
              {/* Output */}
              {run.output && (
                <div>
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                    Output
                  </p>
                  <div className="bg-gray-800 border border-gray-700 rounded-xl p-4 text-sm text-gray-200 whitespace-pre-wrap">
                    {run.output}
                  </div>
                </div>
              )}

              {/* Error */}
              {run.error && (
                <div>
                  <p className="text-xs font-semibold text-red-500 uppercase tracking-wider mb-2">
                    Error
                  </p>
                  <div className="bg-red-900/20 border border-red-800 rounded-xl p-4 text-sm text-red-300 font-mono whitespace-pre-wrap">
                    {run.error}
                  </div>
                </div>
              )}

              {/* Trace */}
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                  Execution trace ({run.trace.length} events)
                </p>
                <RunTraceView trace={run.trace} />
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
