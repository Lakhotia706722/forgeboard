/**
 * Workspace member management API — Phase 9b.
 */
import { api } from './api'
import type { WorkspaceRole } from './authApi'

export type WorkspaceMemberStatus = 'pending' | 'active'

export interface MemberOut {
  user_id: string
  email: string
  full_name: string
  role: WorkspaceRole
  status: WorkspaceMemberStatus
  joined_at: string | null
  created_at: string
}

export interface WorkspaceDetailOut {
  id: string
  name: string
  slug: string
  description: string | null
  is_active: boolean
  spend_cap_usd_cents: number
  created_at: string
  updated_at: string
}

export interface WorkspaceSettingsUpdate {
  name?: string
  description?: string
  spend_cap_usd_cents?: number
}

export const workspaceApi = {
  // Settings
  getDetail: (): Promise<WorkspaceDetailOut> =>
    api.get<WorkspaceDetailOut>('/workspaces/me').then((r) => r.data),

  updateSettings: (data: WorkspaceSettingsUpdate): Promise<WorkspaceDetailOut> =>
    api.patch<WorkspaceDetailOut>('/workspaces/me', data).then((r) => r.data),

  // Members
  listMembers: (): Promise<MemberOut[]> =>
    api.get<MemberOut[]>('/workspaces/me/members').then((r) => r.data),

  inviteMember: (email: string, role: WorkspaceRole): Promise<MemberOut> =>
    api
      .post<MemberOut>('/workspaces/me/members', { email, role })
      .then((r) => r.data),

  updateMemberRole: (userId: string, role: WorkspaceRole): Promise<MemberOut> =>
    api
      .patch<MemberOut>(`/workspaces/me/members/${userId}`, { role })
      .then((r) => r.data),

  removeMember: (userId: string): Promise<void> =>
    api.delete(`/workspaces/me/members/${userId}`).then(() => undefined),
}
