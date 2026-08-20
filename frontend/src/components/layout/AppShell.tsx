import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Building2, Cpu, LayoutDashboard, LogOut, Phone, Plug, Settings, Shield, Store } from 'lucide-react'
import toast from 'react-hot-toast'

import { useAuthStore } from '@/store/authStore'
import { authApi } from '@/lib/authApi'
import { cn } from '@/lib/utils'
import { useBranding } from '@/hooks/useBranding'
import WorkspaceSwitcher from '@/components/workspace/WorkspaceSwitcher'
import PendingInviteBanner from '@/components/workspace/PendingInviteBanner'

interface AppShellProps {
  children: React.ReactNode
}

const BASE_NAV = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/board', label: 'Agents', icon: Cpu },
  { to: '/marketplace', label: 'Marketplace', icon: Store },
  { to: '/connectors', label: 'Connectors', icon: Plug },
  { to: '/voice', label: 'Voice', icon: Phone },
  { to: '/governance', label: 'Governance', icon: Shield },
  { to: '/settings', label: 'Settings', icon: Settings },
]

const AGENCY_NAV = { to: '/agency', label: 'Agency', icon: Building2 }

export default function AppShell({ children }: AppShellProps) {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, clearAuth } = useAuthStore()
  const branding = useBranding()

  // Show Agency link only when user has at least one agency membership
  const isAgency = user?.workspaces.some((w) => w.role === 'agency')
  const navItems = isAgency ? [...BASE_NAV, AGENCY_NAV] : BASE_NAV

  const appName = branding?.brand_app_name ?? 'ForgeBoard'
  const logoUrl = branding?.brand_logo_url ?? null

  async function handleLogout() {
    try {
      await authApi.logout()
    } catch {
      // Ignore logout API errors — clear client state regardless
    }
    clearAuth()
    toast.success('Signed out.')
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col">
      {/* Top nav */}
      <nav className="border-b border-gray-800 bg-gray-900 px-6 h-14 flex items-center gap-4 flex-shrink-0">
        <Link to="/dashboard" className="flex items-center gap-2 mr-1 text-white tracking-tight">
          {logoUrl ? (
            <img
              src={logoUrl}
              alt={`${appName} logo`}
              className="h-7 w-auto max-w-[120px] object-contain"
            />
          ) : (
            <span className="text-base font-bold">⚒ {appName}</span>
          )}
        </Link>

        {/* Workspace switcher */}
        <WorkspaceSwitcher />

        <div className="flex items-center gap-1 flex-1">
          {navItems.map(({ to, label, icon: Icon }) => (
            <Link
              key={to}
              to={to}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors',
                location.pathname === to
                  ? 'bg-gray-800 text-white'
                  : 'text-gray-400 hover:text-gray-100 hover:bg-gray-800/60',
              )}
            >
              <Icon size={14} aria-hidden="true" />
              {label}
            </Link>
          ))}
        </div>

        <div className="flex items-center gap-3">
          {user && (
            <span className="text-sm text-gray-500 hidden sm:block">
              {user.full_name}
            </span>
          )}
          <button
            onClick={handleLogout}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm text-gray-400 hover:text-gray-100 hover:bg-gray-800/60 transition-colors"
            aria-label="Sign out"
          >
            <LogOut size={14} aria-hidden="true" />
            <span className="hidden sm:block">Sign out</span>
          </button>
        </div>
      </nav>

      {/* Pending invite banner — shown just below nav when invites exist */}
      <PendingInviteBanner />

      {/* Page content */}
      <main className="flex-1">{children}</main>
    </div>
  )
}
