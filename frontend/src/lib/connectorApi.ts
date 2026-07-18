import { api } from './api'

export type ConnectorType = 'http_webhook' | 'google_calendar' | 'gmail' | 'kv_store'
export type ConnectorStatus = 'connected' | 'disconnected' | 'error' | 'pending_auth'

export interface ConnectorOut {
  id: string
  workspace_id: string
  name: string
  connector_type: ConnectorType
  status: ConnectorStatus
  config_json: Record<string, string> | null
  last_checked_at: string | null
  last_error: string | null
  created_at: string
  updated_at: string
}

export interface KvEntry {
  key: string
  value: string
}

export const connectorApi = {
  list: (): Promise<ConnectorOut[]> =>
    api.get<ConnectorOut[]>('/connectors').then((r) => r.data),

  get: (id: string): Promise<ConnectorOut> =>
    api.get<ConnectorOut>(`/connectors/${id}`).then((r) => r.data),

  delete: (id: string): Promise<void> =>
    api.delete(`/connectors/${id}`).then(() => undefined),

  createHttp: (data: {
    name?: string
    webhook_url?: string
    secret?: string
    secret_header_name?: string
  }): Promise<ConnectorOut> =>
    api.post<ConnectorOut>('/connectors/http', data).then((r) => r.data),

  createKv: (data?: { name?: string }): Promise<ConnectorOut> =>
    api.post<ConnectorOut>('/connectors/kv', data ?? {}).then((r) => r.data),

  createGoogleCalendar: (data?: {
    name?: string
    calendar_id?: string
  }): Promise<ConnectorOut> =>
    api.post<ConnectorOut>('/connectors/google-calendar', data ?? {}).then((r) => r.data),

  createGmail: (data?: { name?: string; sender_name?: string }): Promise<ConnectorOut> =>
    api.post<ConnectorOut>('/connectors/gmail', data ?? {}).then((r) => r.data),

  healthCheck: (id: string): Promise<ConnectorOut> =>
    api.post<ConnectorOut>(`/connectors/${id}/health-check`).then((r) => r.data),

  // KV store
  kvList: (connectorId: string): Promise<KvEntry[]> =>
    api
      .get<{ entries: KvEntry[] }>(`/connectors/${connectorId}/kv`)
      .then((r) => r.data.entries),

  kvGet: (connectorId: string, key: string): Promise<KvEntry> =>
    api.get<KvEntry>(`/connectors/${connectorId}/kv/${key}`).then((r) => r.data),

  kvSet: (connectorId: string, key: string, value: string): Promise<KvEntry> =>
    api
      .put<KvEntry>(`/connectors/${connectorId}/kv/${key}`, { key, value })
      .then((r) => r.data),

  kvDelete: (connectorId: string, key: string): Promise<void> =>
    api.delete(`/connectors/${connectorId}/kv/${key}`).then(() => undefined),

  /** Redirect URL to kick off Google OAuth for a connector */
  googleOAuthUrl: (connectorId: string) =>
    `/api/v1/connectors/oauth/google/init/${connectorId}`,
}
