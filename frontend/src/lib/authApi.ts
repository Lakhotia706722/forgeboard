/**
 * Auth API calls — thin wrappers over the Axios instance.
 * Phase 9a: UserOut now returns workspaces[] (list) + legacy workspace (first active).
 */
import { api } from './api'

export type WorkspaceRole = 'owner' | 'admin' | 'builder' | 'viewer' | 'agency'
export type WorkspaceMemberStatus = 'pending' | 'active'

export interface WorkspaceOut {
  id: string
  name: string
  slug: string
  description: string | null
  created_at: string
  role: WorkspaceRole | null
  member_status: WorkspaceMemberStatus | null
}

export interface UserOut {
  id: string
  email: string
  full_name: string
  is_active: boolean
  created_at: string
  /** All workspaces the user belongs to (active + pending invites) */
  workspaces: WorkspaceOut[]
  /** Deprecated: first active workspace. Use workspaces[] instead. */
  workspace: WorkspaceOut | null
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface AuthResponse {
  user: UserOut
  tokens: TokenPair
}

export interface WorkspaceCreate {
  name: string
  description?: string
}

export const authApi = {
  signup: (data: {
    email: string
    full_name: string
    password: string
  }): Promise<AuthResponse> =>
    api.post<AuthResponse>('/auth/signup', data).then((r) => r.data),

  login: (data: {
    email: string
    password: string
  }): Promise<AuthResponse> =>
    api.post<AuthResponse>('/auth/login', data).then((r) => r.data),

  refresh: (refresh_token: string): Promise<TokenPair> =>
    api.post<TokenPair>('/auth/refresh', { refresh_token }).then((r) => r.data),

  logout: (): Promise<void> =>
    api.post('/auth/logout').then(() => undefined),

  me: (): Promise<UserOut> =>
    api.get<UserOut>('/auth/me').then((r) => r.data),

  // Workspace management
  listWorkspaces: (): Promise<WorkspaceOut[]> =>
    api.get<WorkspaceOut[]>('/auth/workspaces').then((r) => r.data),

  createWorkspace: (data: WorkspaceCreate): Promise<WorkspaceOut> =>
    api.post<WorkspaceOut>('/auth/workspaces', data).then((r) => r.data),

  acceptInvite: (workspaceId: string): Promise<WorkspaceOut> =>
    api.post<WorkspaceOut>(`/auth/workspaces/${workspaceId}/accept`).then((r) => r.data),
}
