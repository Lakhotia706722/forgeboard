import { useEffect, useState } from 'react'
import { Navigate, Outlet } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { authApi } from '@/lib/authApi'
import AppShell from './layout/AppShell'

/**
 * Guards protected routes.
 * - Redirects to /login if no access token in store.
 * - On mount, validates the token by calling /auth/me and refreshes user data.
 *   If /me fails (expired token) the Axios interceptor handles refresh automatically;
 *   if that also fails, it clears auth and redirects to /login.
 */
export default function ProtectedRoute() {
  const { accessToken, setUser, clearAuth } = useAuthStore()
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    if (!accessToken) {
      setChecking(false)
      return
    }

    authApi
      .me()
      .then((user) => {
        setUser(user)
      })
      .catch(() => {
        // Refresh already attempted by interceptor and failed
        clearAuth()
      })
      .finally(() => setChecking(false))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  if (!accessToken) {
    return <Navigate to="/login" replace />
  }

  if (checking) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-gray-700 border-t-forge-500" />
      </div>
    )
  }

  return (
    <AppShell>
      <Outlet />
    </AppShell>
  )
}
