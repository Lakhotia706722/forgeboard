import { useState } from 'react'
import { X, Globe, Mail, Calendar, Database } from 'lucide-react'
import toast from 'react-hot-toast'
import { connectorApi, type ConnectorOut } from '@/lib/connectorApi'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import { cn } from '@/lib/utils'

type Step = 'pick' | 'configure'

type ConnectorDef = {
  type: 'http_webhook' | 'google_calendar' | 'gmail' | 'kv_store'
  label: string
  icon: React.ElementType
  description: string
  requiresOAuth: boolean
}

const CONNECTOR_DEFS: ConnectorDef[] = [
  {
    type: 'http_webhook',
    label: 'HTTP / Webhook',
    icon: Globe,
    description: 'Connect any service via HTTP requests or webhooks.',
    requiresOAuth: false,
  },
  {
    type: 'google_calendar',
    label: 'Google Calendar',
    icon: Calendar,
    description: 'Read and write calendar events.',
    requiresOAuth: true,
  },
  {
    type: 'gmail',
    label: 'Gmail',
    icon: Mail,
    description: 'Send emails via your Google account.',
    requiresOAuth: true,
  },
  {
    type: 'kv_store',
    label: 'Notes Store',
    icon: Database,
    description: 'Internal key-value memory — no setup required.',
    requiresOAuth: false,
  },
]

interface AddConnectorModalProps {
  onClose: () => void
  onAdded: (connector: ConnectorOut) => void
}

export default function AddConnectorModal({ onClose, onAdded }: AddConnectorModalProps) {
  const [step, setStep] = useState<Step>('pick')
  const [selected, setSelected] = useState<ConnectorDef | null>(null)
  const [loading, setLoading] = useState(false)

  // Form fields
  const [name, setName] = useState('')
  const [webhookUrl, setWebhookUrl] = useState('')
  const [secret, setSecret] = useState('')
  const [calendarId, setCalendarId] = useState('primary')
  const [senderName, setSenderName] = useState('')

  function handlePick(def: ConnectorDef) {
    setSelected(def)
    setName(def.label)
    setStep('configure')
  }

  async function handleSubmit() {
    if (!selected) return
    setLoading(true)
    try {
      let connector: ConnectorOut

      if (selected.type === 'http_webhook') {
        connector = await connectorApi.createHttp({
          name: name || selected.label,
          webhook_url: webhookUrl || undefined,
          secret: secret || undefined,
        })
      } else if (selected.type === 'kv_store') {
        connector = await connectorApi.createKv({ name: name || selected.label })
      } else if (selected.type === 'google_calendar') {
        connector = await connectorApi.createGoogleCalendar({
          name: name || selected.label,
          calendar_id: calendarId || 'primary',
        })
      } else {
        // gmail
        connector = await connectorApi.createGmail({
          name: name || selected.label,
          sender_name: senderName || undefined,
        })
      }

      onAdded(connector)
      toast.success(`${connector.name} added.`)

      // Redirect to Google OAuth immediately if needed
      if (selected.requiresOAuth) {
        toast('Redirecting to Google to authorise…', { icon: '🔑' })
        setTimeout(() => {
          window.location.href = connectorApi.googleOAuthUrl(connector.id)
        }, 1200)
      }

      onClose()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to add connector.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Add connector"
    >
      <div className="w-full max-w-lg bg-gray-900 border border-gray-800 rounded-2xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <h2 className="font-semibold text-white">
            {step === 'pick' ? 'Add a connector' : `Configure ${selected?.label}`}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-300 transition-colors"
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="p-6">
          {step === 'pick' && (
            <div className="grid grid-cols-2 gap-3">
              {CONNECTOR_DEFS.map((def) => {
                const Icon = def.icon
                return (
                  <button
                    key={def.type}
                    onClick={() => handlePick(def)}
                    className={cn(
                      'flex flex-col items-start gap-2 p-4 rounded-xl border text-left',
                      'bg-gray-800/50 border-gray-700',
                      'hover:bg-gray-800 hover:border-gray-600 transition-colors',
                    )}
                  >
                    <div className="p-1.5 rounded-lg bg-gray-700">
                      <Icon size={16} className="text-forge-400" aria-hidden="true" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-white">{def.label}</p>
                      <p className="text-xs text-gray-500 mt-0.5 leading-snug">{def.description}</p>
                    </div>
                    {def.requiresOAuth && (
                      <span className="text-xs text-yellow-500">Requires Google auth</span>
                    )}
                  </button>
                )
              })}
            </div>
          )}

          {step === 'configure' && selected && (
            <div className="space-y-4">
              <Input
                label="Connector name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={selected.label}
              />

              {selected.type === 'http_webhook' && (
                <>
                  <Input
                    label="Webhook URL (optional)"
                    type="url"
                    value={webhookUrl}
                    onChange={(e) => setWebhookUrl(e.target.value)}
                    placeholder="https://your-endpoint.com/hook"
                  />
                  <Input
                    label="Signing secret (optional)"
                    type="password"
                    value={secret}
                    onChange={(e) => setSecret(e.target.value)}
                    placeholder="Stored encrypted"
                  />
                </>
              )}

              {selected.type === 'google_calendar' && (
                <Input
                  label="Calendar ID"
                  value={calendarId}
                  onChange={(e) => setCalendarId(e.target.value)}
                  placeholder="primary"
                />
              )}

              {selected.type === 'gmail' && (
                <Input
                  label="Sender display name (optional)"
                  value={senderName}
                  onChange={(e) => setSenderName(e.target.value)}
                  placeholder="ForgeBoard Agent"
                />
              )}

              {selected.type === 'kv_store' && (
                <p className="text-sm text-gray-400">
                  The notes store is internal — no credentials required. It's ready to use
                  immediately after adding.
                </p>
              )}

              {selected.requiresOAuth && (
                <div className="rounded-lg bg-yellow-900/20 border border-yellow-800 px-4 py-3 text-sm text-yellow-300">
                  After adding, you'll be redirected to Google to grant access.
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        {step === 'configure' && (
          <div className="px-6 py-4 border-t border-gray-800 flex justify-end gap-3">
            <Button variant="secondary" size="sm" onClick={() => setStep('pick')}>
              Back
            </Button>
            <Button size="sm" loading={loading} onClick={handleSubmit}>
              {selected?.requiresOAuth ? 'Add & Authorise' : 'Add connector'}
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
