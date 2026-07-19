import { Globe, Mail, Calendar, Database } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ConnectorOut } from '@/lib/connectorApi'

const TYPE_ICONS: Record<string, React.ElementType> = {
  http_webhook: Globe,
  google_calendar: Calendar,
  gmail: Mail,
  kv_store: Database,
}

const STATUS_DOT: Record<string, string> = {
  connected:    'bg-green-400',
  disconnected: 'bg-gray-500',
  error:        'bg-red-400',
  pending_auth: 'bg-yellow-400',
}

interface ConnectorPickerProps {
  connectors: ConnectorOut[]
  selected: string[]
  onChange: (ids: string[]) => void
}

export default function ConnectorPicker({
  connectors,
  selected,
  onChange,
}: ConnectorPickerProps) {
  function toggle(id: string) {
    if (selected.includes(id)) {
      onChange(selected.filter((s) => s !== id))
    } else {
      onChange([...selected, id])
    }
  }

  if (connectors.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-gray-700 px-4 py-6 text-center text-sm text-gray-600">
        No connectors yet.{' '}
        <a href="/connectors" className="text-forge-400 hover:text-forge-300">
          Add one first.
        </a>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
      {connectors.map((conn) => {
        const Icon = TYPE_ICONS[conn.connector_type] ?? Globe
        const isSelected = selected.includes(conn.id)
        const dotClass = STATUS_DOT[conn.status] ?? 'bg-gray-500'

        return (
          <button
            key={conn.id}
            type="button"
            onClick={() => toggle(conn.id)}
            className={cn(
              'flex items-center gap-3 rounded-xl border p-3 text-left transition-colors',
              isSelected
                ? 'border-forge-500 bg-forge-900/30'
                : 'border-gray-700 bg-gray-800/40 hover:border-gray-600',
            )}
            aria-pressed={isSelected}
          >
            <div
              className={cn(
                'p-1.5 rounded-lg flex-shrink-0',
                isSelected ? 'bg-forge-800' : 'bg-gray-700',
              )}
            >
              <Icon
                size={14}
                className={isSelected ? 'text-forge-300' : 'text-gray-400'}
                aria-hidden="true"
              />
            </div>
            <div className="flex-1 min-w-0">
              <p
                className={cn(
                  'text-sm font-medium truncate',
                  isSelected ? 'text-white' : 'text-gray-300',
                )}
              >
                {conn.name}
              </p>
              <p className="text-xs text-gray-500 capitalize">
                {conn.connector_type.replace('_', ' ')}
              </p>
            </div>
            <span
              className={cn('h-2 w-2 rounded-full flex-shrink-0', dotClass)}
              aria-label={conn.status}
            />
          </button>
        )
      })}
    </div>
  )
}
