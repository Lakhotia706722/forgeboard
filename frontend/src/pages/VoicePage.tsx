import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Phone, Mic, Clock, AlertTriangle, Download } from 'lucide-react'

import AppShell from '@/components/layout/AppShell'
import CallStatusBadge from '@/components/voice/CallStatusBadge'
import CallLogDrawer from '@/components/voice/CallLogDrawer'
import TranscriptSearchBar from '@/components/voice/TranscriptSearchBar'
import { voiceApi, formatDuration, type CallLogOut } from '@/lib/voiceApi'
import { cn } from '@/lib/utils'

function formatDate(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function ComplianceDot({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 text-xs',
        ok ? 'text-green-400' : 'text-yellow-400',
      )}
      title={label}
      aria-label={`${label}: ${ok ? 'yes' : 'no'}`}
    >
      <span
        className={cn('h-1.5 w-1.5 rounded-full flex-shrink-0', ok ? 'bg-green-400' : 'bg-yellow-400')}
        aria-hidden="true"
      />
      {label}
    </span>
  )
}

/** Client-side filter: match on from/to numbers or transcript text */
function filterCalls(calls: CallLogOut[], query: string): CallLogOut[] {
  if (!query.trim()) return calls
  const q = query.toLowerCase()
  return calls.filter((c) => {
    if (c.from_number.includes(q) || c.to_number.includes(q)) return true
    if (c.call_sid.toLowerCase().includes(q)) return true
    return c.transcript.some((t) => t.text.toLowerCase().includes(q))
  })
}

export default function VoicePage() {
  const [search, setSearch] = useState('')
  const [selectedCallId, setSelectedCallId] = useState<string | null>(null)
  const [page, setPage] = useState(0)
  const PAGE_SIZE = 25

  const { data: calls = [], isLoading, isError } = useQuery({
    queryKey: ['calls-all'],
    queryFn: () => voiceApi.listAllCalls(200),
    refetchInterval: 10_000, // refresh every 10s to catch newly completed calls
  })

  const filtered = useMemo(() => filterCalls(calls, search), [calls, search])
  const paginated = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)
  const totalPages = Math.ceil(filtered.length / PAGE_SIZE)

  // Reset to page 0 when search changes
  const handleSearch = (v: string) => {
    setSearch(v)
    setPage(0)
  }

  return (
    <AppShell>
      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-bold text-white flex items-center gap-2">
              <Phone size={18} className="text-forge-400" aria-hidden="true" />
              Voice &amp; Calls
            </h1>
            <p className="text-sm text-gray-500 mt-0.5">
              Call archive — transcripts, recordings, compliance flags
            </p>
          </div>

          {/* Stats summary */}
          {!isLoading && (
            <div className="hidden sm:flex items-center gap-6 text-sm text-gray-500">
              <span>
                <span className="text-white font-medium">{calls.length}</span> total calls
              </span>
              <span>
                <span className="text-white font-medium">
                  {calls.filter((c) => c.status === 'in_progress').length}
                </span>{' '}
                live now
              </span>
              <span>
                <span className="text-white font-medium">
                  {calls.filter((c) => !c.ai_disclosed).length}
                </span>{' '}
                missing disclosure
              </span>
            </div>
          )}
        </div>

        {/* Search */}
        <TranscriptSearchBar
          value={search}
          onChange={handleSearch}
          className="mb-4 max-w-md"
        />

        {/* Table */}
        {isLoading && (
          <div className="flex items-center justify-center py-20 text-gray-600">
            <div
              className="h-5 w-5 animate-spin rounded-full border-2 border-gray-700 border-t-forge-500"
              role="status"
              aria-label="Loading calls"
            />
          </div>
        )}

        {isError && (
          <div className="flex items-center gap-2 py-8 text-red-400 text-sm">
            <AlertTriangle size={14} aria-hidden="true" />
            Failed to load call logs. Check your connection.
          </div>
        )}

        {!isLoading && !isError && filtered.length === 0 && (
          <div className="text-center py-20 text-gray-600">
            <Mic size={32} className="mx-auto mb-3 opacity-30" aria-hidden="true" />
            <p className="text-sm">
              {search ? 'No calls match your search.' : 'No calls recorded yet.'}
            </p>
          </div>
        )}

        {!isLoading && !isError && filtered.length > 0 && (
          <>
            <div className="rounded-xl border border-gray-800 overflow-hidden">
              <table className="w-full text-sm" role="table" aria-label="Call log archive">
                <thead>
                  <tr className="border-b border-gray-800 bg-gray-900/60">
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                      Direction
                    </th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                      From
                    </th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                      To
                    </th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                      Duration
                    </th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                      Started
                    </th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                      Compliance
                    </th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                      Recording
                    </th>
                    <th className="px-4 py-3" aria-label="Actions" />
                  </tr>
                </thead>
                <tbody>
                  {paginated.map((call, i) => (
                    <tr
                      key={call.id}
                      className={cn(
                        'border-b border-gray-800/60 hover:bg-gray-800/30 transition-colors cursor-pointer',
                        i === paginated.length - 1 && 'border-b-0',
                      )}
                      onClick={() => setSelectedCallId(call.id)}
                      role="row"
                      aria-label={`Call from ${call.from_number} to ${call.to_number}`}
                    >
                      <td className="px-4 py-3">
                        <CallStatusBadge status={call.status} />
                      </td>
                      <td className="px-4 py-3 text-gray-400 capitalize">
                        {call.direction}
                      </td>
                      <td className="px-4 py-3 font-mono text-gray-300 text-xs">
                        {call.from_number}
                      </td>
                      <td className="px-4 py-3 font-mono text-gray-300 text-xs">
                        {call.to_number}
                      </td>
                      <td className="px-4 py-3 text-gray-400">
                        <span className="flex items-center gap-1">
                          <Clock size={11} aria-hidden="true" className="text-gray-600" />
                          {formatDuration(call.duration_seconds)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-500 text-xs whitespace-nowrap">
                        {formatDate(call.started_at)}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-col gap-0.5">
                          <ComplianceDot ok={call.consent_verified} label="Consent" />
                          <ComplianceDot ok={call.dnc_checked} label="DNC" />
                          <ComplianceDot ok={call.ai_disclosed} label="Disclosed" />
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        {call.recording_url ? (
                          <a
                            href={call.recording_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="flex items-center gap-1 text-xs text-forge-400 hover:text-forge-300 transition-colors"
                            aria-label="Download recording"
                          >
                            <Download size={11} aria-hidden="true" />
                            .mp3
                          </a>
                        ) : (
                          <span className="text-xs text-gray-700">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            setSelectedCallId(call.id)
                          }}
                          className="text-xs text-gray-500 hover:text-gray-200 transition-colors px-2 py-1 rounded hover:bg-gray-800"
                          aria-label={`View call details for ${call.from_number}`}
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between mt-4 text-sm text-gray-500">
                <span>
                  Showing {page * PAGE_SIZE + 1}–
                  {Math.min((page + 1) * PAGE_SIZE, filtered.length)} of {filtered.length}
                </span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPage((p) => Math.max(0, p - 1))}
                    disabled={page === 0}
                    className="px-3 py-1 rounded border border-gray-700 hover:bg-gray-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                    aria-label="Previous page"
                  >
                    Prev
                  </button>
                  <span className="text-gray-600">
                    {page + 1} / {totalPages}
                  </span>
                  <button
                    onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                    disabled={page === totalPages - 1}
                    className="px-3 py-1 rounded border border-gray-700 hover:bg-gray-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                    aria-label="Next page"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Call detail drawer */}
      {selectedCallId && (
        <CallLogDrawer
          callLogId={selectedCallId}
          onClose={() => setSelectedCallId(null)}
        />
      )}
    </AppShell>
  )
}
