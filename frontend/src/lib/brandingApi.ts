/**
 * White-label branding API — Phase 9d.
 */
import { api } from './api'

export interface BrandingOut {
  workspace_id: string
  display_name: string | null
  brand_logo_url: string | null
  brand_primary_color: string | null
  brand_app_name: string | null
  managed_by_agency_id: string | null
}

export interface BrandingUpdate {
  display_name?: string | null
  brand_logo_url?: string | null
  brand_primary_color?: string | null
  brand_app_name?: string | null
}

export const brandingApi = {
  get: (): Promise<BrandingOut> =>
    api.get<BrandingOut>('/branding').then((r) => r.data),

  update: (data: BrandingUpdate): Promise<BrandingOut> =>
    api.patch<BrandingOut>('/branding', data).then((r) => r.data),

  setManagingAgency: (agencyUserId: string | null): Promise<BrandingOut> =>
    api
      .patch<BrandingOut>('/branding/agency', { agency_user_id: agencyUserId })
      .then((r) => r.data),
}
