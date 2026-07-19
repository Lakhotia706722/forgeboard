import { useState } from 'react'
import { X } from 'lucide-react'
import toast from 'react-hot-toast'

import { agentApi, type AgentCreate, type AgentOut, type TriggerType } from '@/lib/agentApi'
import type { ConnectorOut } from '@/lib/connectorApi'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import ConnectorPicker from './ConnectorPicker'
import TriggerConfig from './TriggerConfig'

interface AgentBuilderModalProps {
  connectors: ConnectorOut[]
  onClose: () => void
  onCreated: (agent: AgentOut) => void
  /** If provided, edit mode — pre-fills fields and calls update instead */
  editAgent?: AgentOut
}

export default function AgentBuilderModal({
  connectors,
  onClose,
  onCreated,
  editAgent,
}: AgentBuilderModalProps) {
  const isEdit = Boolean(editAgent)

  const [name, setName] = useState(editAgent?.name ?? '')
  const [goal, setGoal] = useState(editAgent?.goal ?? '')
  const [selectedConnectors, setSelectedConnectors] = useState<string[]>(
    editAgent?.connectors.map((c) => c.id) ?? [],
  )
  const [triggerType, setTriggerType] = useState<TriggerType>(
    editAgent?.trigger_type ?? 'manual',
  )
  const [cronSchedule, setCronSchedule] = useState(editAgent?.cron_schedule ?? '')
  const [requiresApproval, setRequiresApproval] = useState(
    editAgent?.requires_approval ?? false,
  )
  const [loading, setLoading] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})

  function validate(): boolean {
    const next: Record<string, string> = {}
    if (!name.trim()) next.name = 'Name is required.'
    if (!goal.trim()) next.goal = 'Goal description is required.'
    else if (goal.trim().length < 10) next.goal = 'Goal must be at least 10 characters.'
    if (triggerType === 'scheduled' && !cronSchedule.trim()) {
      next.cron = 'Cron schedule is required for scheduled agents.'
    }
    setErrors(next)
    return Object.keys(next).length === 0
  }

  async function handleSubmit() {
    if (!validate()) return
    setLoading(true)

    try {
      const payload: AgentCreate = {
        name: name.trim(),
        goal: goal.trim(),
        connector_ids: selectedConnectors,
        trigger_type: triggerType,
        cron_schedule: triggerType === 'scheduled' ? cronSchedule.trim() : undefined,
        requires_approval: requiresApproval,
      }

      let agent: AgentOut
      if (isEdit && editAgent) {
        agent = await agentApi.update(editAgent.id, payload)
        toast.success(`"${agent.name}" updated.`)
      } else {
        agent = await agentApi.create(payload)
        toast.success(`"${agent.name}" created as Draft.`)
      }

      onCreated(agent)
      onClose()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save agent.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      role="dialog"
      aria-modal="true"
      aria-label={isEdit ? 'Edit agent' : 'Create agent'}
    >
      <div className="w-full max-w-2xl bg-gray-900 border border-gray-800 rounded-2xl shadow-2xl flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800 flex-shrink-0">
          <h2 className="font-semibold text-white">
            {isEdit ? `Edit "${editAgent!.name}"` : 'Build a new agent'}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-300 transition-colors"
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>

        {/* Scrollable body */}
        <div className="overflow-y-auto flex-1 p-6 space-y-6">
          {/* Name */}
          <Input
            label="Agent name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            error={errors.name}
            placeholder="e.g. Daily calendar summariser"
          />

          {/* Goal */}
          <div className="space-y-1">
            <label className="block text-sm font-medium text-gray-300">
              What should this agent do?
            </label>
            <textarea
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              rows={5}
              placeholder="Describe the agent's job in plain language. Be specific about what it should check, decide, and do.

Example: Every weekday morning, fetch my Google Calendar events for the day, summarise them into a brief agenda, and email it to me at jane@example.com."
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 placeholder:text-gray-600 focus:outline-none focus:ring-2 focus:ring-forge-500 focus:border-forge-500 resize-none hover:border-gray-600 transition-colors"
              aria-invalid={errors.goal ? 'true' : undefined}
            />
            {errors.goal && (
              <p role="alert" className="text-xs text-red-400">{errors.goal}</p>
            )}
            <p className="text-xs text-gray-600">{goal.length} / 4000 characters</p>
          </div>

          {/* Connector picker */}
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-300">
              Connected tools
              <span className="ml-1 font-normal text-gray-500">(optional)</span>
            </label>
            <ConnectorPicker
              connectors={connectors}
              selected={selectedConnectors}
              onChange={setSelectedConnectors}
            />
          </div>

          {/* Trigger */}
          <TriggerConfig
            triggerType={triggerType}
            onTriggerTypeChange={setTriggerType}
            cronSchedule={cronSchedule}
            onCronScheduleChange={setCronSchedule}
            cronError={errors.cron}
          />

          {/* Approval gate */}
          <label className="flex items-start gap-3 cursor-pointer group">
            <input
              type="checkbox"
              checked={requiresApproval}
              onChange={(e) => setRequiresApproval(e.target.checked)}
              className="mt-0.5 h-4 w-4 rounded border-gray-600 bg-gray-800 text-forge-500 focus:ring-forge-500"
            />
            <div>
              <p className="text-sm font-medium text-gray-300 group-hover:text-white transition-colors">
                Require approval before tool calls execute
              </p>
              <p className="text-xs text-gray-600 mt-0.5">
                When enabled, the agent pauses and waits for manual approval before each
                action. Surfaced in the board (Phase 6).
              </p>
            </div>
          </label>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-800 flex justify-end gap-3 flex-shrink-0">
          <Button variant="secondary" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button size="sm" loading={loading} onClick={handleSubmit}>
            {isEdit ? 'Save changes' : 'Create agent'}
          </Button>
        </div>
      </div>
    </div>
  )
}
