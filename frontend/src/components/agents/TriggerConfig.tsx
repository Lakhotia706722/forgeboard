import type { TriggerType } from '@/lib/agentApi'
import { cn } from '@/lib/utils'
import Input from '@/components/ui/Input'

const TRIGGERS: { value: TriggerType; label: string; description: string }[] = [
  { value: 'manual', label: 'Manual', description: 'Run on demand from the board.' },
  { value: 'scheduled', label: 'Scheduled', description: 'Run on a cron schedule.' },
  { value: 'webhook', label: 'Webhook', description: 'Triggered by an inbound HTTP call.' },
]

interface TriggerConfigProps {
  triggerType: TriggerType
  onTriggerTypeChange: (v: TriggerType) => void
  cronSchedule: string
  onCronScheduleChange: (v: string) => void
  cronError?: string
}

export default function TriggerConfig({
  triggerType,
  onTriggerTypeChange,
  cronSchedule,
  onCronScheduleChange,
  cronError,
}: TriggerConfigProps) {
  return (
    <div className="space-y-3">
      <label className="block text-sm font-medium text-gray-300">Trigger</label>

      <div className="grid grid-cols-3 gap-3">
        {TRIGGERS.map((t) => (
          <button
            key={t.value}
            type="button"
            onClick={() => onTriggerTypeChange(t.value)}
            className={cn(
              'flex flex-col items-start gap-1 rounded-xl border p-3 text-left transition-colors',
              triggerType === t.value
                ? 'border-forge-500 bg-forge-900/30 text-white'
                : 'border-gray-700 bg-gray-800/40 text-gray-400 hover:border-gray-600 hover:text-gray-200',
            )}
          >
            <span className="text-sm font-medium">{t.label}</span>
            <span className="text-xs leading-snug opacity-70">{t.description}</span>
          </button>
        ))}
      </div>

      {triggerType === 'scheduled' && (
        <div className="space-y-2">
          <Input
            label="Cron schedule"
            value={cronSchedule}
            onChange={(e) => onCronScheduleChange(e.target.value)}
            placeholder="0 9 * * 1-5  (weekdays at 9am)"
            error={cronError}
          />
          <p className="text-xs text-gray-600">
            Standard 5-field cron: minute hour day month weekday.{' '}
            <a
              href="https://crontab.guru"
              target="_blank"
              rel="noopener noreferrer"
              className="text-forge-500 hover:text-forge-400"
            >
              crontab.guru
            </a>
          </p>
        </div>
      )}

      {triggerType === 'webhook' && (
        <p className="text-xs text-gray-500 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2">
          A unique webhook URL will be generated when the agent goes Live.
        </p>
      )}
    </div>
  )
}
