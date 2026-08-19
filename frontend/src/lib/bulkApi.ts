/**
 * Bulk action API client — Phase 9e.
 */
import { api } from './api'
import type { AgentStatus } from './agentApi'

export interface BulkActionResult {
  succeeded: string[]
  failed: Array<{ agent_id: string; reason: string }>
  total: number
  success_count: number
  failure_count: number
}

export const bulkApi = {
  updateStatus: (
    agentIds: string[],
    status: AgentStatus,
    confirmLive = false,
  ): Promise<BulkActionResult> =>
    api
      .post<BulkActionResult>('/bulk/agents/status', {
        agent_ids: agentIds,
        status,
        confirm_live: confirmLive,
      })
      .then((r) => r.data),

  deleteAgents: (agentIds: string[], confirmLive = false): Promise<BulkActionResult> =>
    api
      .post<BulkActionResult>('/bulk/agents/delete', {
        agent_ids: agentIds,
        confirm_live: confirmLive,
      })
      .then((r) => r.data),

  cloneAgents: (
    agentIds: string[],
    sourceWorkspaceId: string,
    destWorkspaceId: string,
  ): Promise<BulkActionResult> =>
    api
      .post<BulkActionResult>('/bulk/agents/clone', {
        agent_ids: agentIds,
        source_workspace_id: sourceWorkspaceId,
        dest_workspace_id: destWorkspaceId,
      })
      .then((r) => r.data),
}
