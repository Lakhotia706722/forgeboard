import { Navigate, Outlet } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'

/**
 * Redirects already-authenticated users away from login/signup pages
 * directly to the dashboard.
 */
export default function GuestRoute() {
  const token = useAuthStore((s) => s.accessToken)
  return token ? <Navigate to="/dashboard" replace /> : <Outlet />
}
