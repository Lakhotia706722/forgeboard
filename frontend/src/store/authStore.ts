import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { UserOut, WorkspaceOut } from '@/lib/authApi'

interface AuthState {
  accessToken: string | null
  refreshToken: string | null
  user: UserOut | null
  /** The workspace the user is currently operating in */
  activeWorkspaceId: string | null

  setAuth: (access: string, refresh: string, user: UserOut) => void
  setUser: (user: UserOut) => void
  clearAuth: () => void
  isAuthenticated: () => boolean

  /** Switch to a different workspace */
  setActiveWorkspace: (workspaceId: string) => void

  /** Convenience: return the full WorkspaceOut for the active workspace */
  activeWorkspace: () => WorkspaceOut | null

  /** Pending invites the user hasn't accepted yet */
  pendingInvites: () => WorkspaceOut[]
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      activeWorkspaceId: null,

      setAuth: (access, refresh, user) => {
        // Auto-select the first active workspace on login
        const firstActive = user.workspaces.find(
          (w) => w.member_status === 'active',
        )
        set({
          accessToken: access,
          refreshToken: refresh,
          user,
          activeWorkspaceId: firstActive?.id ?? null,
        })
      },

      setUser: (user) => {
        const { activeWorkspaceId } = get()
        // Keep the active workspace if it still exists in the new user data
        const stillValid = user.workspaces.some(
          (w) => w.id === activeWorkspaceId && w.member_status === 'active',
        )
        if (!stillValid) {
          const firstActive = user.workspaces.find(
            (w) => w.member_status === 'active',
          )
          set({ user, activeWorkspaceId: firstActive?.id ?? null })
        } else {
          set({ user })
        }
      },

      clearAuth: () =>
        set({ accessToken: null, refreshToken: null, user: null, activeWorkspaceId: null }),

      isAuthenticated: () => Boolean(get().accessToken),

      setActiveWorkspace: (workspaceId: string) => {
        const { user } = get()
        const ws = user?.workspaces.find(
          (w) => w.id === workspaceId && w.member_status === 'active',
        )
        if (!ws) return
        set({ activeWorkspaceId: workspaceId })
      },

      activeWorkspace: () => {
        const { user, activeWorkspaceId } = get()
        if (!user || !activeWorkspaceId) return null
        return user.workspaces.find((w) => w.id === activeWorkspaceId) ?? null
      },

      pendingInvites: () => {
        const { user } = get()
        return user?.workspaces.filter((w) => w.member_status === 'pending') ?? []
      },
    }),
    {
      name: 'forgeboard-auth',
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        user: state.user,
        activeWorkspaceId: state.activeWorkspaceId,
      }),
    },
  ),
)
