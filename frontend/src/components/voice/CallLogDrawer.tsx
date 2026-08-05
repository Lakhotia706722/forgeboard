import { X, Phone, Clock, User, Bot, Download } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { voiceApi, formatDuration } from '@/lib/voiceApi'
import CallStatusBadge from './CallStatusBadge'
import { cn } from '@/lib/utils'

interface CallLogDrawerProps {
  callLogId: string
  onClose: () => void
}

function formatTs(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

export default function CallLogDrawer({ callLogId, onClose }: CallLogDrawerProps) {
  const { data: call, isLoading } = useQuery({
    queryKey: ['call', callLogId],
    queryFn: () => voiceApi.getCall(callLogId),
    refetchInterval: (q) =>
      q.state.data?.status === 'in_progress' || q.state.data?.status === 'ringing' ? 3000 : false,
  })

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} aria-hidden="true" />
      <aside className="relative z-50 w-full max-w-md bg-gray-900 border-l border-gray-800 flex flex-col h-full shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800 flex-shrink-0">
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-0.5">Call Detail</p>
            <div className="flex items-center gap-2">
              <Phone size={14} className="text-forge-400" />
              {call && <CallStatusBadge status={call.status} />}
            </div>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-200 transition-colors" aria-label="Close">
            <X size={18} />
          </button>
        </div>

        {isLoading && (
          <div className="flex items-center justify-center flex-1 text-gray-600">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-gray-700 border-t-forge-500" />
          </div>
        )}

        {call && (
          <div className="flex-1 overflow-y-auto">
            {/* Stats bar */}
            <div className="grid grid-cols-3 gap-px bg-gray-800 border-b border-gray-800">
              {[
                { label: 'Duration', value: formatDuration(call.duration_seconds) },
                { label: 'Direction', value: call.direction },
                { label: 'AI Disclosed', value: call.ai_disclosed ? 'Yes' : 'No' },
              ].map(({ label, value }) => (
                <div key={label} className="bg-gray-900 px-3 py-2.5 text-center">
                  <p className="text-sm font-bold text-white">{value}</p>
                  <p className="text-xs text-gray-500 mt-0.5">{label}</p>
                </div>
              ))}
            </div>

            <div className="px-5 py-4 space-y-5">
              {/* Numbers */}
              <div className="space-y-1.5 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">From</span>
                  <span className="text-gray-300 font-mono">{call.from_number}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">To</span>
                  <span className="text-gray-300 font-mono">{call.to_number}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Started</span>
                  <span className="text-gray-300">{formatTs(call.started_at)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Ended</span>
                  <span className="text-gray-300">{formatTs(call.ended_at)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Call SID</span>
                  <span className="text-gray-500 font-mono text-xs">{call.call_sid}</span>
                </div>
                {call.recording_url && (
                  <div className="flex justify-between items-center">
                    <span className="text-gray-500">Recording</span>
                    <a
                      href={call.recording_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 text-xs text-forge-400 hover:text-forge-300 transition-colors"
                      aria-label="Download call recording"
                    >
                      <Download size={11} aria-hidden="true" />
                      Download .mp3
                    </a>
                  </div>
                )}
              </div>

              {/* Compliance indicators */}
              <div className="space-y-2">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Compliance</p>
                {[
                  { label: 'Consent verified', ok: call.consent_verified },
                  { label: 'DNC checked', ok: call.dnc_checked },
                  { label: 'AI disclosed', ok: call.ai_disclosed },
                ].map(({ label, ok }) => (
                  <div key={label} className="flex items-center justify-between text-sm">
                    <span className="text-gray-400">{label}</span>
                    <span className={cn('text-xs font-medium', ok ? 'text-green-400' : 'text-yellow-400')}>
                      {ok ? '✓ Yes' : '⚠ No'}
                    </span>
                  </div>
                ))}
              </div>

              {/* Transcript */}
              {call.transcript.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    Transcript ({call.transcript.length} turns)
                  </p>
                  <div className="space-y-2 max-h-96 overflow-y-auto">
                    {call.transcript.map((entry, i) => (
                      <div
                        key={i}
                        className={cn(
                          'flex gap-2 text-sm',
                          entry.speaker === 'agent' ? 'flex-row-reverse' : 'flex-row',
                        )}
                      >
                        <div className={cn(
                          'flex-shrink-0 p-1.5 rounded-full h-6 w-6 flex items-center justify-center',
                          entry.speaker === 'agent' ? 'bg-forge-800' : 'bg-gray-800',
                        )}>
                          {entry.speaker === 'agent'
                            ? <Bot size={12} className="text-forge-300" />
                            : <User size={12} className="text-gray-400" />}
                        </div>
                        <div className={cn(
                          'max-w-[80%] rounded-xl px-3 py-2 text-xs leading-relaxed',
                          entry.speaker === 'agent'
                            ? 'bg-forge-900/40 border border-forge-800 text-forge-100'
                            : 'bg-gray-800 border border-gray-700 text-gray-200',
                        )}>
                          {entry.text}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {call.transcript.length === 0 && call.status === 'completed' && (
                <p className="text-xs text-gray-600 text-center py-4">No transcript recorded.</p>
              )}
            </div>
          </div>
        )}
      </aside>
    </div>
  )
}
