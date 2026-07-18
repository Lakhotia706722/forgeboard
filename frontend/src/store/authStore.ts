import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { UserOut } from '@/lib/authApi'

interface AuthState {
  accessToken: string | null
  refreshToken: string | null
  user: UserOut | null
  setAuth: (access: string, refresh: string, user: UserOut) => void
  setUser: (user: UserOut) => void
  clearAuth: () => void
  isAuthenticated: () => boolean
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      refreshToken: null,
      user: null,

      setAuth: (access, refresh, user) =>
        set({ accessToken: access, refreshToken: refresh, user }),

      setUser: (user) => set({ user }),

      clearAuth: () =>
        set({ accessToken: null, refreshToken: null, user: null }),

      isAuthenticated: () => Boolean(get().accessToken),
    }),
    {
      name: 'forgeboard-auth',
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        user: state.user,
      }),
    },
  ),
)
