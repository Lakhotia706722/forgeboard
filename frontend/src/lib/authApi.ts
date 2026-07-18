/**
 * Auth API calls — thin wrappers over the Axios instance.
 */
import { api } from './api'

export interface WorkspaceOut {
  id: string
  name: string
  slug: string
  created_at: string
}

export interface UserOut {
  id: string
  email: string
  full_name: string
  is_active: boolean
  created_at: string
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
}
