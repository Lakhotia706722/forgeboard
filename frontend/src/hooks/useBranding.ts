/**
 * useBranding — Phase 9d.
 *
 * Fetches the active workspace's branding and applies it to the DOM
 * via CSS custom properties on :root.
 *
 * CSS variables applied:
 *   --brand-primary      hex color  (falls back to forge-500 #6366f1)
 *   --brand-app-name     string     (falls back to "ForgeBoard")
 *
 * The logo URL and display_name are returned for use in AppShell.
 *
 * Note: CSS custom properties only affect components that reference
 * var(--brand-primary) etc.  The Tailwind design tokens (forge-*) are
 * compile-time; runtime branding overrides them via inline CSS variables
 * applied to styled elements that opt in.
 */
import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { brandingApi, type BrandingOut } from '@/lib/brandingApi'
import { useAuthStore } from '@/store/authStore'

const DEFAULT_PRIMARY = '#6366f1'  // forge-500
const DEFAULT_APP_NAME = 'ForgeBoard'

export function useBranding(): BrandingOut | null {
  const activeWorkspaceId = useAuthStore((s) => s.activeWorkspaceId)

  const { data: branding } = useQuery({
    queryKey: ['branding', activeWorkspaceId],
    queryFn: brandingApi.get,
    enabled: !!activeWorkspaceId,
    staleTime: 5 * 60 * 1000, // 5 min — branding rarely changes
  })

  useEffect(() => {
    const root = document.documentElement
    root.style.setProperty(
      '--brand-primary',
      branding?.brand_primary_color ?? DEFAULT_PRIMARY,
    )
    root.style.setProperty(
      '--brand-app-name',
      `"${branding?.brand_app_name ?? DEFAULT_APP_NAME}"`,
    )
  }, [branding?.brand_primary_color, branding?.brand_app_name])

  return branding ?? null
}
