/**
 * BulkActionBar — Phase 9e.
 *
 * Appears at the bottom of the board when one or more agents are selected.
 * Shows count + action buttons with a confirmation step for live-agent actions.
 */
import { useState } from 'react'
import { Pause, Play, Trash2, X, AlertTriangle, CheckCircle2 } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'

import { bulkApi, type BulkActionResult } from '@/lib/bulkApi'
import type { AgentOut, AgentStatus } from '@/lib/agentApi'
import { cn } from '@/lib/utils'

interface BulkActionBarProps {
  selected: AgentOut[]
  onClearSelection: () => void
  onAgentsChange: (agents: AgentOut[]) => void
  allAgents: AgentOut[]
}

interface ConfirmState {
  action: 'pause' | 'resume' | 'delete'
  hasLive: boolean
}

function resultToast(result: BulkActionResult, action: string) {
  if (result.failure_count === 0) {
    toast.success(`${action}: ${result.success_count} agent${result.success_count !== 1 ? 's' : ''} updated.`)
  } else {
    toast.error(
      `${action}: ${result.success_count} succeeded, ${result.failure_count} failed. ` +
        result.failed.map((f) => f.reason).join('; '),
    )
  }
}

export default function BulkActionBar({
  selected,
  onClearSelection,
  onAgentsChange,
  allAgents,
}: BulkActionBarProps) {
  const qc = useQueryClient()
  const [confirm, setConfirm] = useState<ConfirmState | null>(null)

  const selectedIds = selected.map((a) => a.id)
  const liveCount = selected.filter((a) => a.status === 'live').length
  const hasLive = liveCount > 0

  // Helper: apply result to local agent list
  function applyResult(result: BulkActionResult, newStatus?: AgentStatus) {
    if (newStatus) {
      const successSet = new Set(result.succeeded)
      onAgentsChange(
        allAgents.map((a) => (successSet.has(a.id) ? { ...a, status: newStatus } : a)),
      )
    } else {
      // Delete
      const successSet = new Set(result.succeeded)
      onAgentsChange(allAgents.filter((a) => !successSet.has(a.id)))
    }
    onClearSelection()
    qc.invalidateQueries({ queryKey: ['agents'] })
  }

  const pauseMutation = useMutation({
    mutationFn: (confirmLive: boolean) =>
      bulkApi.updateStatus(selectedIds, 'paused', confirmLive),
    onSuccess: (result) => {
      resultToast(result, 'Bulk pause')
      applyResult(result, 'paused')
      setConfirm(null)
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Bulk pause failed.'),
  })

  const resumeMutation = useMutation({
    mutationFn: (confirmLive: boolean) =>
      bulkApi.updateStatus(selectedIds, 'live', confirmLive),
    onSuccess: (result) => {
      resultToast(result, 'Bulk resume')
      applyResult(result, 'live')
      setConfirm(null)
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Bulk resume failed.'),
  })

  const deleteMutation = useMutation({
    mutationFn: (confirmLive: boolean) =>
      bulkApi.deleteAgents(selectedIds, confirmLive),
    onSuccess: (result) => {
      resultToast(result, 'Bulk delete')
      applyResult(result)
      setConfirm(null)
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Bulk delete failed.'),
  })

  function handleAction(action: 'pause' | 'resume' | 'delete') {
    if (hasLive) {
      // Always require confirmation when live agents are in the selection
      setConfirm({ action, hasLive: true })
    } else {
      // No live agents — execute immediately
      executeAction(action, false)
    }
  }

  function executeAction(action: 'pause' | 'resume' | 'delete', confirmLive: boolean) {
    if (action === 'pause') pauseMutation.mutate(confirmLive)
    else if (action === 'resume') resumeMutation.mutate(confirmLive)
    else deleteMutation.mutate(confirmLive)
  }

  const isPending =
    pauseMutation.isPending || resumeMutation.isPending || deleteMutation.isPending

  return (
    <>
      {/* Bulk action bar — fixed bottom */}
      <div
        className="fixed bottom-6 left-1/2 -translate-x-1/2 z-30"
        role="toolbar"
        aria-label="Bulk actions"
      >
        <div className="flex items-center gap-3 bg-gray-900 border border-gray-700 rounded-2xl px-5 py-3 shadow-2xl">
          {/* Count badge */}
          <span className="flex items-center gap-1.5 text-sm font-medium text-white">
            <CheckCircle2 size={14} className="text-forge-400" aria-hidden="true" />
            {selected.length} selected
          </span>

          {hasLive && (
            <span className="flex items-center gap-1 text-xs text-amber-400">
              <AlertTriangle size={11} aria-hidden="true" />
              {liveCount} live
            </span>
          )}

          <div className="w-px h-5 bg-gray-700" aria-hidden="true" />

          {/* Pause */}
          <button
            onClick={() => handleAction('pause')}
            disabled={isPending}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-gray-300 hover:bg-gray-800 hover:text-white disabled:opacity-50 transition-colors"
            aria-label="Pause selected agents"
          >
            <Pause size={12} aria-hidden="true" />
            Pause
          </button>

          {/* Resume */}
          <button
            onClick={() => handleAction('resume')}
            disabled={isPending}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-gray-300 hover:bg-gray-800 hover:text-white disabled:opacity-50 transition-colors"
            aria-label="Resume selected agents"
          >
            <Play size={12} aria-hidden="true" />
            Resume
          </button>

          {/* Delete */}
          <button
            onClick={() => handleAction('delete')}
            disabled={isPending}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-red-400 hover:bg-red-900/20 hover:text-red-300 disabled:opacity-50 transition-colors"
            aria-label="Delete selected agents"
          >
            <Trash2 size={12} aria-hidden="true" />
            Delete
          </button>

          <div className="w-px h-5 bg-gray-700" aria-hidden="true" />

          {/* Clear selection */}
          <button
            onClick={onClearSelection}
            className="text-gray-500 hover:text-gray-300 transition-colors"
            aria-label="Clear selection"
          >
            <X size={14} aria-hidden="true" />
          </button>
        </div>
      </div>

      {/* Confirmation modal — shown when live agents are affected */}
      {confirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setConfirm(null)}
            aria-hidden="true"
          />
          <div
            className="relative z-50 bg-gray-900 border border-gray-700 rounded-2xl p-6 w-full max-w-sm shadow-2xl"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="confirm-title"
          >
            <div className="flex items-start gap-3 mb-4">
              <AlertTriangle
                size={20}
                className="text-amber-400 flex-shrink-0 mt-0.5"
                aria-hidden="true"
              />
              <div>
                <h3 id="confirm-title" className="font-semibold text-white text-sm">
                  {confirm.action === 'delete' ? 'Confirm bulk delete' : 'Confirm bulk status change'}
                </h3>
                <p className="text-sm text-gray-400 mt-1">
                  {liveCount} of the selected agents{' '}
                  {liveCount === 1 ? 'is' : 'are'} currently{' '}
                  <span className="text-green-400 font-medium">Live</span>.{' '}
                  {confirm.action === 'delete'
                    ? 'Deleting live agents will stop all active triggers immediately.'
                    : confirm.action === 'pause'
                    ? 'Pausing live agents will stop all active triggers immediately.'
                    : 'Resuming agents will re-enable their triggers.'}
                </p>
              </div>
            </div>

            <div className="flex gap-2">
              <button
                onClick={() => executeAction(confirm.action, true)}
                disabled={isPending}
                className={cn(
                  'flex-1 py-2 text-sm font-medium rounded-lg transition-colors disabled:opacity-50',
                  confirm.action === 'delete'
                    ? 'bg-red-600 hover:bg-red-500 text-white'
                    : 'bg-amber-600 hover:bg-amber-500 text-white',
                )}
              >
                {isPending
                  ? 'Processing…'
                  : `Yes, ${confirm.action} ${selected.length} agent${selected.length !== 1 ? 's' : ''}`}
              </button>
              <button
                onClick={() => setConfirm(null)}
                className="px-4 py-2 text-sm text-gray-500 hover:text-gray-300 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
