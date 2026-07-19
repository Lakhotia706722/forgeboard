import { api } from './api'

export type RunStatus = 'pending' | 'running' | 'success' | 'failed' | 'cancelled'

export interface TraceEvent {
  seq: number
  type: string
  timestamp: string
  data: Record<string, unknown>
}

export interface RunOut {
  id: string
  agent_id: string
  workspace_id: string
  status: RunStatus
  trigger_source: string
  celery_task_id: string | null
  output: string | null
  error: string | null
  input_tokens: number
  output_tokens: number
  cost_usd_cents: number
  started_at: string | null
  finished_at: string | null
  created_at: string
}

export interface RunDetail extends RunOut {
  trace: TraceEvent[]
}

export const runApi = {
  trigger: (agentId: string): Promise<RunOut> =>
    api.post<RunOut>(`/agents/${agentId}/runs`).then((r) => r.data),

  listForAgent: (agentId: string, limit = 50): Promise<RunOut[]> =>
    api
      .get<RunOut[]>(`/agents/${agentId}/runs`, { params: { limit } })
      .then((r) => r.data),

  listAll: (limit = 50, agentId?: string): Promise<RunOut[]> =>
    api
      .get<RunOut[]>('/runs', { params: { limit, agent_id: agentId } })
      .then((r) => r.data),

  get: (runId: string): Promise<RunDetail> =>
    api.get<RunDetail>(`/runs/${runId}`).then((r) => r.data),
}
