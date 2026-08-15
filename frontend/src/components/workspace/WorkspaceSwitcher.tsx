import { useState } from 'react'
import { ChevronDown, Plus, Check, Clock } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'

import { useAuthStore } from '@/store/authStore'
import { authApi, type WorkspaceCreate } from '@/lib/authApi'
import { cn } from '@/lib/utils'

export default function WorkspaceSwitcher() {
  const [open, setOpen] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState('')

  const { user, activeWorkspaceId, setActiveWorkspace, setUser } = useAuthStore()
  const queryClient = useQueryClient()

  const activeWorkspaces = user?.workspaces.filter((w) => w.member_status === 'active') ?? []
  const current = activeWorkspaces.find((w) => w.id === activeWorkspaceId)

  const createMutation = useMutation({
    mutationFn: (data: WorkspaceCreate) => authApi.createWorkspace(data),
    onSuccess: async (newWs) => {
      // Refresh user data to include the new workspace
      const updated = await authApi.me()
      setUser(updated)
      setActiveWorkspace(newWs.id)
      // Invalidate all workspace-scoped queries
      queryClient.clear()
      setShowCreate(false)
      setNewName('')
      setOpen(false)
      toast.success(`Switched to "${newWs.name}"`)
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : 'Failed to create workspace'),
  })

  async function handleSwitch(workspaceId: string) {
    if (workspaceId === activeWorkspaceId) {
      setOpen(false)
      return
    }
    setActiveWorkspace(workspaceId)
    // Invalidate all workspace-scoped cached data
    queryClient.clear()
    setOpen(false)
    const ws = activeWorkspaces.find((w) => w.id === workspaceId)
    if (ws) toast.success(`Switched to "${ws.name}"`)
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    if (!newName.trim()) return
    createMutation.mutate({ name: newName.trim() })
  }

  if (!user) return null

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className={cn(
          'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors',
          'text-gray-300 hover:text-white hover:bg-gray-800/60',
          'max-w-[180px]',
        )}
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-label="Switch workspace"
      >
        <span className="truncate font-medium">
          {current?.name ?? 'Select workspace'}
        </span>
        <ChevronDown
          size={13}
          className={cn('flex-shrink-0 transition-transform', open && 'rotate-180')}
          aria-hidden="true"
        />
      </button>

      {open && (
        <>
          {/* Click-away overlay */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => { setOpen(false); setShowCreate(false) }}
            aria-hidden="true"
          />

          {/* Dropdown */}
          <div
            className="absolute left-0 top-full mt-1.5 z-50 w-64 bg-gray-900 border border-gray-700 rounded-xl shadow-2xl overflow-hidden"
            role="listbox"
            aria-label="Workspaces"
          >
            <div className="px-3 py-2 border-b border-gray-800">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                Workspaces
              </p>
            </div>

            <ul className="max-h-64 overflow-y-auto py-1">
              {activeWorkspaces.map((ws) => (
                <li key={ws.id}>
                  <button
                    onClick={() => handleSwitch(ws.id)}
                    role="option"
                    aria-selected={ws.id === activeWorkspaceId}
                    className={cn(
                      'w-full flex items-center justify-between px-3 py-2.5 text-sm transition-colors',
                      ws.id === activeWorkspaceId
                        ? 'bg-forge-900/40 text-forge-300'
                        : 'text-gray-300 hover:bg-gray-800 hover:text-white',
                    )}
                  >
                    <div className="flex-1 min-w-0 text-left">
                      <p className="truncate font-medium">{ws.name}</p>
                      {ws.role && (
                        <p className="text-xs text-gray-600 capitalize">{ws.role}</p>
                      )}
                    </div>
                    {ws.id === activeWorkspaceId && (
                      <Check size={13} className="flex-shrink-0 text-forge-400 ml-2" aria-hidden="true" />
                    )}
                  </button>
                </li>
              ))}
            </ul>

            {/* Create new workspace */}
            <div className="border-t border-gray-800 p-2">
              {showCreate ? (
                <form onSubmit={handleCreate} className="flex gap-1.5">
                  <input
                    autoFocus
                    type="text"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    placeholder="Workspace name"
                    className={cn(
                      'flex-1 bg-gray-800 border border-gray-700 rounded-lg',
                      'px-2 py-1.5 text-xs text-gray-200 placeholder-gray-600',
                      'focus:outline-none focus:ring-1 focus:ring-forge-500',
                    )}
                    aria-label="New workspace name"
                    maxLength={255}
                  />
                  <button
                    type="submit"
                    disabled={!newName.trim() || createMutation.isPending}
                    className="px-2 py-1.5 text-xs bg-forge-600 hover:bg-forge-500 disabled:opacity-50 text-white rounded-lg transition-colors"
                    aria-label="Create workspace"
                  >
                    {createMutation.isPending ? '…' : 'Create'}
                  </button>
                </form>
              ) : (
                <button
                  onClick={() => setShowCreate(true)}
                  className="w-full flex items-center gap-2 px-2 py-2 text-xs text-gray-500 hover:text-gray-300 hover:bg-gray-800 rounded-lg transition-colors"
                >
                  <Plus size={12} aria-hidden="true" />
                  New workspace
                </button>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
