import { api } from './api'

export type VoiceMode = 'inbound' | 'outbound'
export type CallStatus = 'idle' | 'ringing' | 'in_progress' | 'completed' | 'failed' | 'transferred'

export interface VoiceAgentOut {
  id: string
  agent_id: string
  workspace_id: string
  phone_number: string | null
  voice_mode: VoiceMode
  tts_voice_id: string | null
  stt_language: string
  max_concurrent_calls: number
  total_calls: number
  total_call_seconds: number
  total_escalations: number
  created_at: string
  updated_at: string
}

export interface TranscriptEntry {
  speaker: string
  text: string
  timestamp_ms: number
}

export interface CallLogOut {
  id: string
  voice_agent_id: string
  workspace_id: string
  run_id: string | null
  call_sid: string
  from_number: string
  to_number: string
  direction: string
  status: CallStatus
  duration_seconds: number
  transcript: TranscriptEntry[]
  consent_verified: boolean
  dnc_checked: boolean
  ai_disclosed: boolean
  started_at: string | null
  ended_at: string | null
  created_at: string
}

export interface VoiceAgentCreate {
  agent_id: string
  phone_number?: string
  voice_mode?: VoiceMode
  tts_voice_id?: string
  stt_language?: string
  max_concurrent_calls?: number
}

export interface VoiceAgentUpdate {
  phone_number?: string
  voice_mode?: VoiceMode
  tts_voice_id?: string
  stt_language?: string
  max_concurrent_calls?: number
}

export const voiceApi = {
  // Voice agents
  createVoiceAgent: (data: VoiceAgentCreate): Promise<VoiceAgentOut> =>
    api.post<VoiceAgentOut>('/voice/agents', data).then((r) => r.data),

  listVoiceAgents: (): Promise<VoiceAgentOut[]> =>
    api.get<VoiceAgentOut[]>('/voice/agents').then((r) => r.data),

  getVoiceAgent: (id: string): Promise<VoiceAgentOut> =>
    api.get<VoiceAgentOut>(`/voice/agents/${id}`).then((r) => r.data),

  updateVoiceAgent: (id: string, data: VoiceAgentUpdate): Promise<VoiceAgentOut> =>
    api.patch<VoiceAgentOut>(`/voice/agents/${id}`, data).then((r) => r.data),

  deleteVoiceAgent: (id: string): Promise<void> =>
    api.delete(`/voice/agents/${id}`).then(() => undefined),

  // Outbound calling
  placeCall: (voiceAgentId: string, to: string, overrideMessage?: string): Promise<CallLogOut> =>
    api
      .post<CallLogOut>(`/voice/agents/${voiceAgentId}/call`, {
        to,
        override_message: overrideMessage,
      })
      .then((r) => r.data),

  // Call logs
  listAgentCalls: (voiceAgentId: string, limit = 50): Promise<CallLogOut[]> =>
    api
      .get<CallLogOut[]>(`/voice/agents/${voiceAgentId}/calls`, { params: { limit } })
      .then((r) => r.data),

  listAllCalls: (limit = 50): Promise<CallLogOut[]> =>
    api.get<CallLogOut[]>('/voice/calls', { params: { limit } }).then((r) => r.data),

  getCall: (callLogId: string): Promise<CallLogOut> =>
    api.get<CallLogOut>(`/voice/calls/${callLogId}`).then((r) => r.data),
}

// Utility — format duration as mm:ss
export function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}
