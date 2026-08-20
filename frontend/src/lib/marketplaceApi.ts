/**
 * Marketplace API client — Phase 10.
 * Public catalog endpoints require no auth.
 * Install, submit, and admin endpoints require auth + X-Workspace-ID.
 */
import { api } from './api'

export type ListingType = 'agent' | 'connector'
export type ListingStatus = 'draft' | 'pending' | 'approved' | 'rejected'

export interface ListingOut {
  id: string
  name: string
  description: string
  category: string
  author_name: string
  listing_type: ListingType
  status: ListingStatus
  version: string
  preview_image_url: string | null
  install_count: number
  created_at: string
  updated_at: string
}

export interface ListingDetail extends ListingOut {
  config_payload: Record<string, unknown>
}

export interface InstallResult {
  listing_id: string
  listing_name: string
  installed_type: ListingType
  agent_id: string | null
  connector_id: string | null
  workspace_id: string
}

export interface ListingSubmit {
  name: string
  description: string
  category: string
  listing_type: ListingType
  config_payload: Record<string, unknown>
  preview_image_url?: string
}

export interface AuthorStats {
  listing_count: number
  total_installs: number
  gross_revenue_usd: number
  platform_take_usd: number
  estimated_payout_usd: number
  take_rate_pct: number
  note: string
  listings: Array<{
    id: string
    name: string
    install_count: number
    estimated_payout_usd: number
  }>
}

export const marketplaceApi = {
  // Public (no auth needed, but api instance will add auth if available)
  listCatalog: (params?: {
    q?: string
    category?: string
    listing_type?: ListingType
    sort?: 'popular' | 'recent'
    limit?: number
    offset?: number
  }): Promise<ListingOut[]> =>
    api.get<ListingOut[]>('/marketplace', { params }).then((r) => r.data),

  listCategories: (): Promise<string[]> =>
    api.get<string[]>('/marketplace/categories').then((r) => r.data),

  getListing: (id: string): Promise<ListingDetail> =>
    api.get<ListingDetail>(`/marketplace/${id}`).then((r) => r.data),

  // Authenticated
  install: (listingId: string): Promise<InstallResult> =>
    api.post<InstallResult>(`/marketplace/${listingId}/install`).then((r) => r.data),

  submit: (data: ListingSubmit): Promise<ListingDetail> =>
    api.post<ListingDetail>('/marketplace/submit', data).then((r) => r.data),

  mySubmissions: (): Promise<ListingDetail[]> =>
    api.get<ListingDetail[]>('/marketplace/my/submissions').then((r) => r.data),

  myStats: (): Promise<AuthorStats> =>
    api.get<AuthorStats>('/marketplace/my/stats').then((r) => r.data),

  // Admin
  listPending: (): Promise<ListingDetail[]> =>
    api.get<ListingDetail[]>('/marketplace/admin/pending').then((r) => r.data),

  review: (
    listingId: string,
    action: 'approve' | 'reject',
    note?: string,
  ): Promise<ListingDetail> =>
    api
      .post<ListingDetail>(`/marketplace/admin/${listingId}/review`, { action, note })
      .then((r) => r.data),
}
