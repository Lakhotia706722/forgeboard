import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Mail, X, Check } from 'lucide-react'
import toast from 'react-hot-toast'

import { useAuthStore } from '@/store/authStore'
import { authApi, type WorkspaceOut } from '@/lib/authApi'
import { cn } from '@/lib/utils'

export default function PendingInviteBanner() {
  const { user, setUser, setActiveWorkspace } = useAuthStore()
  const queryClient = useQueryClient()

  const pending = user?.workspaces.filter((w) => w.member_status === 'pending') ?? []

  const acceptMutation = useMutation({
    mutationFn: (workspaceId: string) => authApi.acceptInvite(workspaceId),
    onSuccess: async (_, workspaceId) => {
      const updated = await authApi.me()
      setUser(updated)
      setActiveWorkspace(workspaceId)
      queryClient.clear()
      toast.success('Joined workspace!')
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : 'Failed to accept invite'),
  })

  if (pending.length === 0) return null

  return (
    <div
      className="bg-forge-900/30 border-b border-forge-800 px-6 py-2"
      role="alert"
      aria-label="Pending workspace invites"
    >
      <div className="max-w-screen-2xl mx-auto flex items-center gap-3 flex-wrap">
        <Mail size={14} className="text-forge-400 flex-shrink-0" aria-hidden="true" />
        <span className="text-sm text-forge-300 font-medium">
          You have {pending.length} pending workspace invite{pending.length > 1 ? 's' : ''}:
        </span>
        <div className="flex items-center gap-2 flex-wrap">
          {pending.map((ws) => (
            <div
              key={ws.id}
              className="flex items-center gap-1.5 bg-gray-900 border border-gray-700 rounded-lg pl-3 pr-1.5 py-1"
            >
              <span className="text-xs text-gray-300">{ws.name}</span>
              {ws.role && (
                <span className="text-xs text-gray-600 capitalize">({ws.role})</span>
              )}
              <button
                onClick={() => acceptMutation.mutate(ws.id)}
                disabled={acceptMutation.isPending}
                className="flex items-center gap-0.5 ml-1 text-xs text-green-400 hover:text-green-300 disabled:opacity-50 transition-colors px-1.5 py-0.5 rounded hover:bg-green-900/20"
                aria-label={`Accept invite to ${ws.name}`}
              >
                <Check size={11} aria-hidden="true" />
                Accept
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
