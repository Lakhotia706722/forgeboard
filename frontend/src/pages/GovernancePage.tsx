import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Download, Shield, DollarSign, AlertTriangle, RefreshCw } from 'lucide-react'
import toast from 'react-hot-toast'

import { governanceApi, type AuditEntry } from '@/lib/governanceApi'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import { cn } from '@/lib/utils'

function formatDate(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

function JsonPreview({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <span className="text-gray-600">—</span>
  return (
    <pre className="text-xs text-gray-400 whitespace-pre-wrap break-words max-w-xs">
      {JSON.stringify(value, null, 2)}
    </pre>
  )
}

export default function GovernancePage() {
  const queryClient = useQueryClient()
  const [capInput, setCapInput] = useState('')

  // ── Spend ────────────────────────────────────────────────────────────────
  const { data: spend, isLoading: spendLoading } = useQuery({
    queryKey: ['spend'],
    queryFn: governanceApi.getSpend,
  })

  const updateCapMutation = useMutation({
    mutationFn: (cents: number) => governanceApi.updateSpendCap(cents),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['spend'] })
      toast.success(`Spend cap updated to $${(data.spend_cap_usd_cents / 100).toFixed(2)}`)
      setCapInput('')
    },
    onError: (err: Error) => toast.error(err.message),
  })

  function handleCapUpdate() {
    const dollars = parseFloat(capInput)
    if (isNaN(dollars) || dollars < 0) {
      toast.error('Enter a valid dollar amount.')
      return
    }
    updateCapMutation.mutate(Math.round(dollars * 100))
  }

  // ── Pending approvals ────────────────────────────────────────────────────
  const { data: approvals = [] } = useQuery({
    queryKey: ['pending-approvals'],
    queryFn: governanceApi.pendingApprovals,
    refetchInterval: 15000,
  })

  // ── Audit log ────────────────────────────────────────────────────────────
  const { data: auditEntries = [], isLoading: auditLoading, refetch: refetchAudit } = useQuery({
    queryKey: ['audit'],
    queryFn: () => governanceApi.auditList({ limit: 200 }),
  })

  return (
    <div className="max-w-5xl mx-auto px-6 py-10 space-y-10">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Shield size={22} className="text-forge-400" /> Governance
        </h1>
        <p className="mt-1 text-sm text-gray-400">
          Audit log, spend cap, and approval controls.
        </p>
      </div>

      {/* Spend cap card */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-gray-300">
          <DollarSign size={16} className="text-forge-400" /> Spend cap
        </div>

        {spendLoading ? (
          <div className="h-8 w-32 bg-gray-800 rounded animate-pulse" />
        ) : spend ? (
          <div className="space-y-3">
            {/* Spend bar */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-400">
                  ${(spend.total_spent_usd_cents / 100).toFixed(2)} spent
                </span>
                <span className="text-gray-500">
                  Cap: ${(spend.spend_cap_usd_cents / 100).toFixed(2)}
                </span>
              </div>
              <div className="h-2 rounded-full bg-gray-800 overflow-hidden">
                <div
                  className={cn(
                    'h-full rounded-full transition-all',
                    spend.cap_reached ? 'bg-red-500' : 'bg-forge-500',
                  )}
                  style={{
                    width: spend.spend_cap_usd_cents > 0
                      ? `${Math.min(100, (spend.total_spent_usd_cents / spend.spend_cap_usd_cents) * 100).toFixed(1)}%`
                      : '0%',
                  }}
                />
              </div>
              {spend.cap_reached && (
                <p className="text-xs text-red-400 flex items-center gap-1">
                  <AlertTriangle size={12} /> Cap reached — all live agents have been auto-paused.
                </p>
              )}
            </div>

            {/* Update cap */}
            <div className="flex items-end gap-3 pt-2 border-t border-gray-800">
              <Input
                label="New cap (USD)"
                type="number"
                min="0"
                step="1"
                value={capInput}
                onChange={(e) => setCapInput(e.target.value)}
                placeholder={`Current: $${(spend.spend_cap_usd_cents / 100).toFixed(2)}`}
                className="w-48"
              />
              <Button
                size="sm"
                loading={updateCapMutation.isPending}
                onClick={handleCapUpdate}
              >
                Update cap
              </Button>
            </div>
          </div>
        ) : null}
      </div>

      {/* Pending approvals */}
      {approvals.length > 0 && (
        <div className="bg-yellow-900/20 border border-yellow-800 rounded-xl p-5 space-y-3">
          <p className="text-sm font-semibold text-yellow-300 flex items-center gap-1.5">
            <AlertTriangle size={15} /> {approvals.length} agent{approvals.length !== 1 ? 's' : ''} awaiting approval
          </p>
          <div className="space-y-2">
            {approvals.map((a) => (
              <div
                key={a.run_id}
                className="flex items-center justify-between bg-gray-900 rounded-lg px-4 py-2.5 text-sm"
              >
                <div>
                  <span className="text-white font-medium">{a.agent_name}</span>
                  <span className="text-gray-500 ml-2 text-xs font-mono">
                    run {a.run_id.slice(0, 8)}
                  </span>
                </div>
                <span className="text-xs text-gray-600">
                  {a.started_at ? formatDate(a.started_at) : '—'}
                </span>
              </div>
            ))}
          </div>
          <p className="text-xs text-yellow-600">
            Go to the Agent Board to approve or reject these runs.
          </p>
        </div>
      )}

      {/* Audit log */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <p className="text-sm font-semibold text-gray-300">
            Audit log
            <span className="ml-2 text-gray-600 font-normal">
              ({auditEntries.length} entries)
            </span>
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => refetchAudit()}
              className="text-gray-500"
            >
              <RefreshCw size={13} /> Refresh
            </Button>
            <a
              href={governanceApi.auditExportUrl('csv')}
              download="audit_log.csv"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-800 border border-gray-700 text-xs text-gray-300 hover:bg-gray-700 hover:text-white transition-colors"
            >
              <Download size={13} /> CSV
            </a>
            <a
              href={governanceApi.auditExportUrl('json')}
              download="audit_log.json"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-800 border border-gray-700 text-xs text-gray-300 hover:bg-gray-700 hover:text-white transition-colors"
            >
              <Download size={13} /> JSON
            </a>
          </div>
        </div>

        {auditLoading && (
          <div className="flex items-center justify-center py-10 text-gray-600">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-gray-700 border-t-forge-500 mr-2" />
            Loading…
          </div>
        )}

        {!auditLoading && auditEntries.length === 0 && (
          <div className="text-center py-10 text-sm text-gray-600 bg-gray-900 border border-gray-800 rounded-xl">
            No tool calls recorded yet. Run an agent to populate the audit log.
          </div>
        )}

        {!auditLoading && auditEntries.length > 0 && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-gray-800 bg-gray-900/80">
                    {['Time', 'Agent', 'Tool', 'Outcome', 'Input', 'Result'].map((h) => (
                      <th
                        key={h}
                        className="px-4 py-2.5 text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {auditEntries.map((entry) => (
                    <tr
                      key={entry.id}
                      className="border-b border-gray-800 hover:bg-gray-800/40 transition-colors align-top"
                    >
                      <td className="px-4 py-2.5 text-xs text-gray-500 whitespace-nowrap">
                        {formatDate(entry.created_at)}
                      </td>
                      <td className="px-4 py-2.5 text-xs text-gray-300 whitespace-nowrap">
                        {entry.agent_name}
                      </td>
                      <td className="px-4 py-2.5 text-xs font-mono text-blue-400 whitespace-nowrap">
                        {entry.tool_name}
                      </td>
                      <td className="px-4 py-2.5">
                        <span
                          className={cn(
                            'text-xs font-medium',
                            entry.outcome === 'success' ? 'text-green-400' : 'text-red-400',
                          )}
                        >
                          {entry.outcome}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 max-w-[180px]">
                        <JsonPreview value={entry.tool_input} />
                      </td>
                      <td className="px-4 py-2.5 max-w-[180px]">
                        <JsonPreview value={entry.tool_result} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
