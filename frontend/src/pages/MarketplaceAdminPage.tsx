import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Shield, CheckCircle2, XCircle, ChevronDown, ChevronUp } from 'lucide-react'
import toast from 'react-hot-toast'

import AppShell from '@/components/layout/AppShell'
import { marketplaceApi, type ListingDetail } from '@/lib/marketplaceApi'
import { useAuthStore } from '@/store/authStore'
import { cn } from '@/lib/utils'

function SubmissionCard({
  listing,
  onReview,
  reviewing,
}: {
  listing: ListingDetail
  onReview: (action: 'approve' | 'reject', note?: string) => void
  reviewing: boolean
}) {
  const [expanded, setExpanded] = useState(false)
  const [rejectNote, setRejectNote] = useState('')
  const [showRejectForm, setShowRejectForm] = useState(false)

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-start justify-between p-4 gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="font-semibold text-white text-sm">{listing.name}</p>
            <span className="text-xs text-gray-600 capitalize">{listing.listing_type}</span>
            <span className="text-xs text-gray-600">·</span>
            <span className="text-xs text-gray-600">{listing.category}</span>
          </div>
          <p className="text-xs text-gray-500 mt-0.5">
            by <span className="text-gray-400">{listing.author_name}</span>
            {' · '}
            {new Date(listing.created_at).toLocaleDateString()}
          </p>
          <p className="text-sm text-gray-400 mt-2 line-clamp-2">{listing.description}</p>
        </div>
        <button
          onClick={() => setExpanded((v) => !v)}
          className="text-gray-500 hover:text-gray-300 transition-colors flex-shrink-0"
          aria-label={expanded ? 'Collapse' : 'Expand config'}
        >
          {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
      </div>

      {/* Config payload — expandable */}
      {expanded && (
        <div className="px-4 pb-3">
          <p className="text-xs text-gray-600 mb-1.5">Config payload</p>
          <pre className="bg-gray-950 border border-gray-800 rounded-lg p-3 text-xs text-gray-400 overflow-x-auto max-h-48 whitespace-pre-wrap">
            {JSON.stringify(listing.config_payload, null, 2)}
          </pre>
        </div>
      )}

      {/* Actions */}
      <div className="border-t border-gray-800 px-4 py-3 flex items-start gap-3">
        {!showRejectForm ? (
          <>
            <button
              onClick={() => onReview('approve')}
              disabled={reviewing}
              className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-medium bg-green-700 hover:bg-green-600 text-white disabled:opacity-50 transition-colors"
              aria-label={`Approve ${listing.name}`}
            >
              <CheckCircle2 size={12} aria-hidden="true" />
              Approve
            </button>
            <button
              onClick={() => setShowRejectForm(true)}
              disabled={reviewing}
              className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-medium bg-red-900/40 hover:bg-red-900/60 text-red-300 disabled:opacity-50 transition-colors"
            >
              <XCircle size={12} aria-hidden="true" />
              Reject
            </button>
          </>
        ) : (
          <div className="flex-1 space-y-2">
            <textarea
              value={rejectNote}
              onChange={(e) => setRejectNote(e.target.value)}
              rows={2}
              placeholder="Reason for rejection (shown to the submitter)…"
              className={cn(
                'w-full bg-gray-800 border border-gray-700 rounded-lg',
                'px-3 py-2 text-xs text-gray-200 placeholder-gray-600 resize-none',
                'focus:outline-none focus:ring-1 focus:ring-red-500',
              )}
              aria-label="Rejection reason"
              autoFocus
            />
            <div className="flex gap-2">
              <button
                onClick={() => {
                  if (!rejectNote.trim()) {
                    toast.error('A rejection note is required.')
                    return
                  }
                  onReview('reject', rejectNote.trim())
                }}
                disabled={reviewing || !rejectNote.trim()}
                className="px-4 py-1.5 text-xs bg-red-700 hover:bg-red-600 text-white rounded-lg disabled:opacity-50 transition-colors"
              >
                {reviewing ? 'Rejecting…' : 'Confirm rejection'}
              </button>
              <button
                onClick={() => { setShowRejectForm(false); setRejectNote('') }}
                className="px-4 py-1.5 text-xs text-gray-500 hover:text-gray-300 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default function MarketplaceAdminPage() {
  const qc = useQueryClient()
  const myRole = useAuthStore((s) => s.activeWorkspace)()?.role
  const canReview = myRole === 'owner' || myRole === 'admin'
  const [reviewingId, setReviewingId] = useState<string | null>(null)

  const { data: pending = [], isLoading } = useQuery({
    queryKey: ['marketplace-pending'],
    queryFn: marketplaceApi.listPending,
    enabled: canReview,
  })

  const reviewMutation = useMutation({
    mutationFn: ({
      id,
      action,
      note,
    }: {
      id: string
      action: 'approve' | 'reject'
      note?: string
    }) => marketplaceApi.review(id, action, note),
    onMutate: ({ id }) => setReviewingId(id),
    onSuccess: (result) => {
      setReviewingId(null)
      qc.invalidateQueries({ queryKey: ['marketplace-pending'] })
      qc.invalidateQueries({ queryKey: ['marketplace'] })
      toast.success(
        result.status === 'approved'
          ? `"${result.name}" approved — now live in the catalog.`
          : `"${result.name}" rejected.`,
      )
    },
    onError: (e) => {
      setReviewingId(null)
      toast.error(e instanceof Error ? e.message : 'Review action failed.')
    },
  })

  return (
    <AppShell>
      <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Shield size={18} className="text-forge-400" aria-hidden="true" />
            Marketplace Review Queue
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Approve or reject third-party listing submissions. Requires admin or owner role.
          </p>
        </div>

        {!canReview && (
          <div className="bg-red-900/20 border border-red-800 rounded-xl px-4 py-3 text-sm text-red-300">
            You need owner or admin role to access the review queue.
          </div>
        )}

        {canReview && isLoading && (
          <div className="flex items-center justify-center py-16 text-gray-600">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-gray-700 border-t-forge-500" />
          </div>
        )}

        {canReview && !isLoading && pending.length === 0 && (
          <div className="text-center py-16 text-gray-600">
            <Shield size={32} className="mx-auto mb-3 opacity-30" aria-hidden="true" />
            <p className="text-sm">No pending submissions.</p>
          </div>
        )}

        {canReview && !isLoading && pending.length > 0 && (
          <>
            <p className="text-xs text-gray-600">
              {pending.length} submission{pending.length !== 1 ? 's' : ''} awaiting review
            </p>
            <div className="space-y-4">
              {pending.map((listing) => (
                <SubmissionCard
                  key={listing.id}
                  listing={listing}
                  reviewing={reviewingId === listing.id}
                  onReview={(action, note) =>
                    reviewMutation.mutate({ id: listing.id, action, note })
                  }
                />
              ))}
            </div>
          </>
        )}
      </div>
    </AppShell>
  )
}
