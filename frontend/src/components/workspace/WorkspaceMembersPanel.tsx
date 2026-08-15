import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { UserPlus, Trash2, ChevronDown } from 'lucide-react'
import toast from 'react-hot-toast'

import { workspaceApi, type MemberOut } from '@/lib/workspaceApi'
import type { WorkspaceRole } from '@/lib/authApi'
import { useAuthStore } from '@/store/authStore'
import { cn } from '@/lib/utils'

const ROLES: WorkspaceRole[] = ['admin', 'builder', 'viewer', 'agency']

const ROLE_BADGE: Record<WorkspaceRole, string> = {
  owner:   'bg-purple-900/40 text-purple-300',
  admin:   'bg-blue-900/40 text-blue-300',
  builder: 'bg-forge-900/40 text-forge-300',
  viewer:  'bg-gray-800 text-gray-400',
  agency:  'bg-amber-900/40 text-amber-300',
}

function RoleBadge({ role }: { role: WorkspaceRole }) {
  return (
    <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium capitalize', ROLE_BADGE[role])}>
      {role}
    </span>
  )
}

function StatusDot({ status }: { status: 'active' | 'pending' }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 text-xs',
        status === 'active' ? 'text-green-400' : 'text-yellow-400',
      )}
    >
      <span
        className={cn(
          'h-1.5 w-1.5 rounded-full',
          status === 'active' ? 'bg-green-400' : 'bg-yellow-400 animate-pulse',
        )}
        aria-hidden="true"
      />
      {status === 'active' ? 'Active' : 'Pending'}
    </span>
  )
}

export default function WorkspaceMembersPanel() {
  const qc = useQueryClient()
  const user = useAuthStore((s) => s.user)
  const activeWorkspace = useAuthStore((s) => s.activeWorkspace)()
  const myRole = activeWorkspace?.role

  const canManage = myRole === 'owner' || myRole === 'admin'

  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState<WorkspaceRole>('viewer')
  const [showInvite, setShowInvite] = useState(false)

  const { data: members = [], isLoading } = useQuery({
    queryKey: ['members'],
    queryFn: workspaceApi.listMembers,
  })

  const inviteMutation = useMutation({
    mutationFn: ({ email, role }: { email: string; role: WorkspaceRole }) =>
      workspaceApi.inviteMember(email, role),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['members'] })
      setInviteEmail('')
      setShowInvite(false)
      toast.success('Invite sent.')
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Invite failed.'),
  })

  const roleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: WorkspaceRole }) =>
      workspaceApi.updateMemberRole(userId, role),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['members'] }),
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Role update failed.'),
  })

  const removeMutation = useMutation({
    mutationFn: (userId: string) => workspaceApi.removeMember(userId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['members'] }),
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Remove failed.'),
  })

  function handleInvite(e: React.FormEvent) {
    e.preventDefault()
    if (!inviteEmail.trim()) return
    inviteMutation.mutate({ email: inviteEmail.trim(), role: inviteRole })
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-white">Members</h2>
        {canManage && (
          <button
            onClick={() => setShowInvite((v) => !v)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-forge-600 hover:bg-forge-500 text-white rounded-lg transition-colors"
            aria-expanded={showInvite}
          >
            <UserPlus size={12} aria-hidden="true" />
            Invite
          </button>
        )}
      </div>

      {/* Invite form */}
      {showInvite && canManage && (
        <form
          onSubmit={handleInvite}
          className="bg-gray-900 border border-gray-700 rounded-xl p-4 space-y-3"
        >
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
            Invite by email
          </p>
          <div className="flex gap-2">
            <input
              type="email"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              placeholder="colleague@example.com"
              required
              className={cn(
                'flex-1 bg-gray-800 border border-gray-700 rounded-lg',
                'px-3 py-2 text-sm text-gray-200 placeholder-gray-600',
                'focus:outline-none focus:ring-1 focus:ring-forge-500',
              )}
              aria-label="Invite email address"
            />
            {/* Role selector */}
            <div className="relative">
              <select
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value as WorkspaceRole)}
                className={cn(
                  'appearance-none bg-gray-800 border border-gray-700 rounded-lg',
                  'pl-3 pr-7 py-2 text-sm text-gray-300 capitalize',
                  'focus:outline-none focus:ring-1 focus:ring-forge-500 cursor-pointer',
                )}
                aria-label="Select role"
              >
                {ROLES.map((r) => (
                  <option key={r} value={r} className="capitalize">
                    {r}
                  </option>
                ))}
              </select>
              <ChevronDown
                size={12}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none"
                aria-hidden="true"
              />
            </div>
          </div>
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={!inviteEmail.trim() || inviteMutation.isPending}
              className="px-4 py-1.5 text-xs bg-forge-600 hover:bg-forge-500 disabled:opacity-50 text-white rounded-lg transition-colors"
            >
              {inviteMutation.isPending ? 'Sending…' : 'Send invite'}
            </button>
            <button
              type="button"
              onClick={() => { setShowInvite(false); setInviteEmail('') }}
              className="px-4 py-1.5 text-xs text-gray-500 hover:text-gray-300 transition-colors"
            >
              Cancel
            </button>
          </div>
          <p className="text-xs text-gray-600">
            The invitee must have a ForgeBoard account. They will see the invite on their next login.
          </p>
        </form>
      )}

      {/* Members list */}
      {isLoading ? (
        <div className="flex items-center justify-center py-8 text-gray-600">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-gray-700 border-t-forge-500" />
        </div>
      ) : (
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <table className="w-full text-sm" role="table" aria-label="Workspace members">
            <thead>
              <tr className="border-b border-gray-800 bg-gray-900/60">
                {['Member', 'Role', 'Status', ''].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {members.map((m, i) => {
                const isMe = m.email === user?.email
                const isOwner = m.role === 'owner'
                return (
                  <tr
                    key={m.user_id}
                    className={cn(
                      'border-b border-gray-800/60',
                      i === members.length - 1 && 'border-b-0',
                    )}
                  >
                    <td className="px-4 py-3">
                      <p className="font-medium text-gray-200 text-sm">
                        {m.full_name}
                        {isMe && (
                          <span className="ml-1.5 text-xs text-gray-600">(you)</span>
                        )}
                      </p>
                      <p className="text-xs text-gray-500">{m.email}</p>
                    </td>
                    <td className="px-4 py-3">
                      {canManage && !isOwner && !isMe ? (
                        <div className="relative inline-block">
                          <select
                            value={m.role}
                            onChange={(e) =>
                              roleMutation.mutate({
                                userId: m.user_id,
                                role: e.target.value as WorkspaceRole,
                              })
                            }
                            disabled={roleMutation.isPending}
                            className={cn(
                              'appearance-none bg-transparent border border-gray-700 rounded-lg',
                              'pl-2 pr-6 py-1 text-xs capitalize text-gray-300',
                              'focus:outline-none focus:ring-1 focus:ring-forge-500 cursor-pointer',
                              ROLE_BADGE[m.role],
                            )}
                            aria-label={`Change ${m.full_name}'s role`}
                          >
                            {ROLES.map((r) => (
                              <option key={r} value={r} className="capitalize bg-gray-900 text-gray-200">
                                {r}
                              </option>
                            ))}
                          </select>
                          <ChevronDown
                            size={10}
                            className="absolute right-1.5 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none"
                            aria-hidden="true"
                          />
                        </div>
                      ) : (
                        <RoleBadge role={m.role} />
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <StatusDot status={m.status} />
                    </td>
                    <td className="px-4 py-3 text-right">
                      {canManage && !isOwner && !isMe && (
                        <button
                          onClick={() => {
                            if (!confirm(`Remove ${m.full_name} from this workspace?`)) return
                            removeMutation.mutate(m.user_id)
                          }}
                          disabled={removeMutation.isPending}
                          className="text-gray-600 hover:text-red-400 disabled:opacity-40 transition-colors"
                          aria-label={`Remove ${m.full_name}`}
                        >
                          <Trash2 size={13} aria-hidden="true" />
                        </button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
