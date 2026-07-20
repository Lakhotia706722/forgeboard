import { api } from './api'

export interface AuditEntry {
  id: string
  agent_id: string
  run_id: string
  agent_name: string
  tool_name: string
  tool_input: unknown
  tool_result: unknown
  outcome: 'success' | 'error'
  created_at: string
}

export interface SpendInfo {
  spend_cap_usd_cents: number
  total_spent_usd_cents: number
  remaining_usd_cents: number
  cap_reached: boolean
}

export interface PendingApproval {
  agent_id: string
  agent_name: string
  run_id: string
  started_at: string | null
}

export const governanceApi = {
  auditList: (params?: { agent_id?: string; run_id?: string; limit?: number }): Promise<AuditEntry[]> =>
    api.get<AuditEntry[]>('/governance/audit', { params }).then((r) => r.data),

  auditExportUrl: (format: 'json' | 'csv', agentId?: string) => {
    const params = new URLSearchParams({ format })
    if (agentId) params.set('agent_id', agentId)
    return `/api/v1/governance/audit/export?${params}`
  },

  getSpend: (): Promise<SpendInfo> =>
    api.get<SpendInfo>('/governance/spend').then((r) => r.data),

  updateSpendCap: (capUsdCents: number): Promise<{ spend_cap_usd_cents: number }> =>
    api
      .patch('/governance/spend-cap', null, { params: { cap_usd_cents: capUsdCents } })
      .then((r) => r.data),

  pendingApprovals: (): Promise<PendingApproval[]> =>
    api.get<PendingApproval[]>('/governance/pending-approvals').then((r) => r.data),
}
