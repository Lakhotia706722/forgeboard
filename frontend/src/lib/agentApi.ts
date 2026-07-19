import { api } from './api'

export type AgentStatus = 'draft' | 'testing' | 'live' | 'paused' | 'needs_review'
export type TriggerType = 'manual' | 'scheduled' | 'webhook'

export interface ConnectorSummary {
  id: string
  name: string
  connector_type: string
  status: string
}

export interface AgentOut {
  id: string
  workspace_id: string
  name: string
  goal: string
  status: AgentStatus
  trigger_type: TriggerType
  cron_schedule: string | null
  requires_approval: boolean
  total_runs: number
  total_cost_usd_cents: number
  consecutive_failures: number
  connectors: ConnectorSummary[]
  created_at: string
  updated_at: string
}

export interface AgentCreate {
  name: string
  goal: string
  connector_ids: string[]
  trigger_type: TriggerType
  cron_schedule?: string
  requires_approval?: boolean
}

export interface AgentUpdate {
  name?: string
  goal?: string
  connector_ids?: string[]
  trigger_type?: TriggerType
  cron_schedule?: string
  requires_approval?: boolean
}

export const agentApi = {
  list: (): Promise<AgentOut[]> =>
    api.get<AgentOut[]>('/agents').then((r) => r.data),

  get: (id: string): Promise<AgentOut> =>
    api.get<AgentOut>(`/agents/${id}`).then((r) => r.data),

  create: (data: AgentCreate): Promise<AgentOut> =>
    api.post<AgentOut>('/agents', data).then((r) => r.data),

  update: (id: string, data: AgentUpdate): Promise<AgentOut> =>
    api.patch<AgentOut>(`/agents/${id}`, data).then((r) => r.data),

  updateStatus: (id: string, status: AgentStatus): Promise<AgentOut> =>
    api.patch<AgentOut>(`/agents/${id}/status`, { status }).then((r) => r.data),

  delete: (id: string): Promise<void> =>
    api.delete(`/agents/${id}`).then(() => undefined),
}
