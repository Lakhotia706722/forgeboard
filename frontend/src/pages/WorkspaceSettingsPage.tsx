import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Settings } from 'lucide-react'
import toast from 'react-hot-toast'

import AppShell from '@/components/layout/AppShell'
import WorkspaceMembersPanel from '@/components/workspace/WorkspaceMembersPanel'
import { workspaceApi } from '@/lib/workspaceApi'
import { useAuthStore } from '@/store/authStore'
import { cn } from '@/lib/utils'

export default function WorkspaceSettingsPage() {
  const qc = useQueryClient()
  const activeWorkspace = useAuthStore((s) => s.activeWorkspace)()
  const { setUser } = useAuthStore()
  const myRole = activeWorkspace?.role
  const canManage = myRole === 'owner' || myRole === 'admin'

  const { data: ws } = useQuery({
    queryKey: ['workspace-detail'],
    queryFn: workspaceApi.getDetail,
  })

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [editingSettings, setEditingSettings] = useState(false)

  // Populate form when data loads
  const handleEditClick = () => {
    setName(ws?.name ?? '')
    setDescription(ws?.description ?? '')
    setEditingSettings(true)
  }

  const settingsMutation = useMutation({
    mutationFn: workspaceApi.updateSettings,
    onSuccess: async () => {
      qc.invalidateQueries({ queryKey: ['workspace-detail'] })
      // Refresh user to update workspace name in switcher
      const { authApi } = await import('@/lib/authApi')
      const updated = await authApi.me()
      setUser(updated)
      setEditingSettings(false)
      toast.success('Settings saved.')
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Save failed.'),
  })

  function handleSaveSettings(e: React.FormEvent) {
    e.preventDefault()
    settingsMutation.mutate({
      name: name.trim() || undefined,
      description: description.trim() || undefined,
    })
  }

  return (
    <AppShell>
      <div className="max-w-3xl mx-auto px-6 py-8 space-y-8">
        {/* Header */}
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Settings size={18} className="text-forge-400" aria-hidden="true" />
            Workspace Settings
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Manage members, roles, and workspace configuration.
          </p>
        </div>

        {/* Workspace info */}
        <section className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-white">General</h2>
            {canManage && !editingSettings && (
              <button
                onClick={handleEditClick}
                className="text-xs text-gray-500 hover:text-gray-300 transition-colors px-3 py-1.5 rounded-lg hover:bg-gray-800"
              >
                Edit
              </button>
            )}
          </div>

          {editingSettings && canManage ? (
            <form onSubmit={handleSaveSettings} className="space-y-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1" htmlFor="ws-name">
                  Name
                </label>
                <input
                  id="ws-name"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  maxLength={255}
                  className={cn(
                    'w-full bg-gray-800 border border-gray-700 rounded-lg',
                    'px-3 py-2 text-sm text-gray-200',
                    'focus:outline-none focus:ring-1 focus:ring-forge-500',
                  )}
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1" htmlFor="ws-desc">
                  Description
                </label>
                <textarea
                  id="ws-desc"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={2}
                  className={cn(
                    'w-full bg-gray-800 border border-gray-700 rounded-lg',
                    'px-3 py-2 text-sm text-gray-200 resize-none',
                    'focus:outline-none focus:ring-1 focus:ring-forge-500',
                  )}
                />
              </div>
              <div className="flex gap-2">
                <button
                  type="submit"
                  disabled={settingsMutation.isPending}
                  className="px-4 py-1.5 text-xs bg-forge-600 hover:bg-forge-500 disabled:opacity-50 text-white rounded-lg transition-colors"
                >
                  {settingsMutation.isPending ? 'Saving…' : 'Save'}
                </button>
                <button
                  type="button"
                  onClick={() => setEditingSettings(false)}
                  className="px-4 py-1.5 text-xs text-gray-500 hover:text-gray-300 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </form>
          ) : (
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-gray-500">Name</dt>
                <dd className="text-gray-300">{ws?.name ?? '—'}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Slug</dt>
                <dd className="text-gray-500 font-mono text-xs">{ws?.slug ?? '—'}</dd>
              </div>
              {ws?.description && (
                <div className="flex justify-between">
                  <dt className="text-gray-500">Description</dt>
                  <dd className="text-gray-300 text-right max-w-xs">{ws.description}</dd>
                </div>
              )}
              <div className="flex justify-between">
                <dt className="text-gray-500">Spend cap</dt>
                <dd className="text-gray-300">
                  ${((ws?.spend_cap_usd_cents ?? 0) / 100).toFixed(2)}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Your role</dt>
                <dd className="text-gray-300 capitalize">{myRole ?? '—'}</dd>
              </div>
            </dl>
          )}
        </section>

        {/* Members */}
        <section className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <WorkspaceMembersPanel />
        </section>
      </div>
    </AppShell>
  )
}
