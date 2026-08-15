/**
 * Agency API client — Phase 9c.
 * These calls do NOT require X-Workspace-ID — they query across workspaces.
 */
import { api } from './api'

export interface AgencyWorkspaceSummary {
  workspace_id: string
  workspace_name: string
  workspace_slug: string
  agent_count: number
  live_agent_count: number
}

export interface AgencyDashboardOut {
  managed_workspace_count: number
  total_agents: number
  total_live_agents: number
  total_runs_last_7d: number
  total_escalations: number
  workspaces: AgencyWorkspaceSummary[]
}

export interface CloneAgentRequest {
  source_workspace_id: string
  source_agent_id: string
  dest_workspace_id: string
  dest_name?: string
}

export interface CloneAgentResult {
  source_agent_id: string
  source_workspace_id: string
  cloned_agent_id: string
  dest_workspace_id: string
  cloned_name: string
}

export const agencyApi = {
  listManagedWorkspaces: (): Promise<AgencyWorkspaceSummary[]> =>
    api.get<AgencyWorkspaceSummary[]>('/agency/workspaces').then((r) => r.data),

  getDashboard: (): Promise<AgencyDashboardOut> =>
    api.get<AgencyDashboardOut>('/agency/dashboard').then((r) => r.data),

  cloneAgent: (data: CloneAgentRequest): Promise<CloneAgentResult> =>
    api.post<CloneAgentResult>('/agency/clone-agent', data).then((r) => r.data),
}
