import { useState } from 'react'
import { Activity, Globe, Mail, Calendar, Database, Trash2, RefreshCw } from 'lucide-react'
import toast from 'react-hot-toast'
import { cn } from '@/lib/utils'
import type { ConnectorOut, ConnectorType } from '@/lib/connectorApi'
import { connectorApi } from '@/lib/connectorApi'
import Button from '@/components/ui/Button'

const TYPE_META: Record<
  ConnectorType,
  { label: string; icon: React.ElementType; description: string }
> = {
  http_webhook: {
    label: 'HTTP / Webhook',
    icon: Globe,
    description: 'Send and receive HTTP requests from any URL.',
  },
  google_calendar: {
    label: 'Google Calendar',
    icon: Calendar,
    description: 'Read events and create calendar entries.',
  },
  gmail: {
    label: 'Gmail',
    icon: Mail,
    description: 'Send emails via your Google account.',
  },
  kv_store: {
    label: 'Notes Store',
    icon: Database,
    description: 'Internal key-value storage for agent memory.',
  },
}

const STATUS_STYLES: Record<
  ConnectorOut['status'],
  { dot: string; label: string }
> = {
  connected:    { dot: 'bg-green-400',  label: 'Connected' },
  disconnected: { dot: 'bg-gray-500',   label: 'Disconnected' },
  error:        { dot: 'bg-red-400',    label: 'Error' },
  pending_auth: { dot: 'bg-yellow-400', label: 'Pending auth' },
}

interface ConnectorCardProps {
  connector: ConnectorOut
  onDeleted: (id: string) => void
  onUpdated: (updated: ConnectorOut) => void
}

export default function ConnectorCard({
  connector,
  onDeleted,
  onUpdated,
}: ConnectorCardProps) {
  const [checking, setChecking] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const meta = TYPE_META[connector.connector_type]
  const statusStyle = STATUS_STYLES[connector.status]
  const Icon = meta.icon

  async function handleHealthCheck() {
    setChecking(true)
    try {
      const updated = await connectorApi.healthCheck(connector.id)
      onUpdated(updated)
      toast.success(`${meta.label}: ${STATUS_STYLES[updated.status].label}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Health check failed.')
    } finally {
      setChecking(false)
    }
  }

  async function handleDelete() {
    if (!confirm(`Remove "${connector.name}"? This cannot be undone.`)) return
    setDeleting(true)
    try {
      await connectorApi.delete(connector.id)
      onDeleted(connector.id)
      toast.success(`${connector.name} removed.`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Delete failed.')
      setDeleting(false)
    }
  }

  function handleGoogleAuth() {
    window.location.href = connectorApi.googleOAuthUrl(connector.id)
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-start gap-3">
        <div className="p-2 rounded-lg bg-gray-800 flex-shrink-0">
          <Icon size={18} className="text-forge-400" aria-hidden="true" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-white truncate">{connector.name}</p>
          <p className="text-xs text-gray-500">{meta.description}</p>
        </div>
        {/* Status badge */}
        <span className="flex items-center gap-1.5 text-xs text-gray-400 flex-shrink-0">
          <span
            className={cn('inline-block h-2 w-2 rounded-full', statusStyle.dot)}
            aria-hidden="true"
          />
          {statusStyle.label}
        </span>
      </div>

      {/* Error message */}
      {connector.last_error && (
        <p className="text-xs text-red-400 bg-red-900/20 border border-red-800 rounded-lg px-3 py-2">
          {connector.last_error}
        </p>
      )}

      {/* Last checked */}
      {connector.last_checked_at && (
        <p className="text-xs text-gray-600">
          Checked{' '}
          {new Date(connector.last_checked_at).toLocaleString(undefined, {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
          })}
        </p>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 mt-auto pt-2 border-t border-gray-800">
        {/* Google OAuth re-auth button */}
        {(connector.connector_type === 'google_calendar' ||
          connector.connector_type === 'gmail') &&
          connector.status !== 'connected' && (
            <Button variant="secondary" size="sm" onClick={handleGoogleAuth}>
              Authorise with Google
            </Button>
          )}

        <Button
          variant="ghost"
          size="sm"
          loading={checking}
          onClick={handleHealthCheck}
          aria-label="Run health check"
          className="text-gray-400"
        >
          <RefreshCw size={13} aria-hidden="true" />
          Check
        </Button>

        <Button
          variant="ghost"
          size="sm"
          loading={deleting}
          onClick={handleDelete}
          aria-label={`Remove ${connector.name}`}
          className="text-red-500 hover:text-red-400 ml-auto"
        >
          <Trash2 size={13} aria-hidden="true" />
          Remove
        </Button>
      </div>
    </div>
  )
}
