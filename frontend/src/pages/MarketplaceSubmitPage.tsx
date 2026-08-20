import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { ArrowLeft, Upload, AlertTriangle, Info } from 'lucide-react'
import toast from 'react-hot-toast'

import AppShell from '@/components/layout/AppShell'
import { marketplaceApi, type ListingType } from '@/lib/marketplaceApi'
import { cn } from '@/lib/utils'

const CATEGORIES = [
  'Productivity', 'Calendar', 'Notifications', 'CRM', 'Finance',
  'HR', 'Marketing', 'DevOps', 'Data', 'Other',
]

const AGENT_PAYLOAD_TEMPLATE = {
  name: 'My Agent Template',
  goal: 'Describe what this agent does in plain language…',
  trigger_type: 'manual',
  cron_schedule: null,
  required_connector_types: ['kv_store'],
  requires_approval: false,
}

const CONNECTOR_PAYLOAD_TEMPLATE = {
  name: 'My Connector Template',
  connector_type: 'http_webhook',
  config: { webhook_url: '' },
}

export default function MarketplaceSubmitPage() {
  const navigate = useNavigate()

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState('Productivity')
  const [listingType, setListingType] = useState<ListingType>('agent')
  const [payloadText, setPayloadText] = useState(
    JSON.stringify(AGENT_PAYLOAD_TEMPLATE, null, 2),
  )
  const [payloadError, setPayloadError] = useState<string | null>(null)
  const [previewUrl, setPreviewUrl] = useState('')

  // Swap template when type changes
  function handleTypeChange(t: ListingType) {
    setListingType(t)
    setPayloadText(
      JSON.stringify(
        t === 'agent' ? AGENT_PAYLOAD_TEMPLATE : CONNECTOR_PAYLOAD_TEMPLATE,
        null,
        2,
      ),
    )
    setPayloadError(null)
  }

  function validatePayload(): Record<string, unknown> | null {
    try {
      const parsed = JSON.parse(payloadText)
      setPayloadError(null)
      return parsed
    } catch (e) {
      setPayloadError('Invalid JSON — check your config payload.')
      return null
    }
  }

  const submitMutation = useMutation({
    mutationFn: marketplaceApi.submit,
    onSuccess: () => {
      toast.success(
        'Submission received! It will appear in your "My Submissions" tab once reviewed.',
      )
      navigate('/marketplace')
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Submission failed.'),
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const payload = validatePayload()
    if (!payload) return
    submitMutation.mutate({
      name: name.trim(),
      description: description.trim(),
      category,
      listing_type: listingType,
      config_payload: payload,
      preview_image_url: previewUrl.trim() || undefined,
    })
  }

  return (
    <AppShell>
      <div className="max-w-2xl mx-auto px-6 py-8">
        <button
          onClick={() => navigate('/marketplace')}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-300 transition-colors mb-6"
        >
          <ArrowLeft size={14} aria-hidden="true" />
          Back to Marketplace
        </button>

        <h1 className="text-xl font-bold text-white flex items-center gap-2 mb-1">
          <Upload size={18} className="text-forge-400" aria-hidden="true" />
          Submit a Listing
        </h1>
        <p className="text-sm text-gray-500 mb-6">
          Share a reusable agent or connector template with the community.
          Submissions are reviewed by the ForgeBoard team before going live.
        </p>

        {/* Security notice */}
        <div className="bg-amber-900/20 border border-amber-800 rounded-xl px-4 py-3 mb-6 flex gap-3">
          <AlertTriangle size={16} className="text-amber-400 flex-shrink-0 mt-0.5" aria-hidden="true" />
          <div className="text-sm text-amber-300 space-y-1">
            <p className="font-medium">Before you submit:</p>
            <ul className="text-xs text-amber-400 space-y-0.5 list-disc list-inside">
              <li>Remove all API keys, OAuth tokens, and passwords from the config</li>
              <li>Replace workspace/agent/connector UUIDs with placeholder text</li>
              <li>The config is scanned automatically — submissions with credentials are rejected</li>
            </ul>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Name */}
          <div>
            <label className="block text-xs font-semibold text-gray-400 mb-1.5" htmlFor="name">
              Name <span className="text-red-400">*</span>
            </label>
            <input
              id="name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              maxLength={255}
              placeholder="e.g. Weekly Sales Report Agent"
              className={cn(
                'w-full bg-gray-900 border border-gray-700 rounded-lg',
                'px-3 py-2 text-sm text-gray-200 placeholder-gray-600',
                'focus:outline-none focus:ring-1 focus:ring-forge-500',
              )}
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-xs font-semibold text-gray-400 mb-1.5" htmlFor="desc">
              Description <span className="text-red-400">*</span>
            </label>
            <textarea
              id="desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              required
              minLength={20}
              maxLength={4000}
              rows={3}
              placeholder="What does this template do? What connectors are needed? Who is it for?"
              className={cn(
                'w-full bg-gray-900 border border-gray-700 rounded-lg',
                'px-3 py-2 text-sm text-gray-200 placeholder-gray-600 resize-none',
                'focus:outline-none focus:ring-1 focus:ring-forge-500',
              )}
            />
            <p className="text-xs text-gray-600 mt-1">{description.length} / 4000</p>
          </div>

          {/* Category + Type row */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-400 mb-1.5" htmlFor="category">
                Category
              </label>
              <select
                id="category"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className={cn(
                  'w-full bg-gray-900 border border-gray-700 rounded-lg',
                  'px-3 py-2 text-sm text-gray-200',
                  'focus:outline-none focus:ring-1 focus:ring-forge-500',
                )}
              >
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-400 mb-1.5">
                Type
              </label>
              <div className="flex gap-2">
                {(['agent', 'connector'] as ListingType[]).map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => handleTypeChange(t)}
                    className={cn(
                      'flex-1 py-2 rounded-lg text-xs font-medium capitalize transition-colors',
                      listingType === t
                        ? 'bg-forge-600 text-white'
                        : 'bg-gray-800 text-gray-400 hover:text-white',
                    )}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Config payload */}
          <div>
            <label className="block text-xs font-semibold text-gray-400 mb-1.5" htmlFor="payload">
              Config payload <span className="text-red-400">*</span>
            </label>
            <div className="flex items-center gap-1.5 text-xs text-gray-600 mb-2">
              <Info size={11} aria-hidden="true" />
              JSON only. No credentials, no workspace/agent/connector IDs.
            </div>
            <textarea
              id="payload"
              value={payloadText}
              onChange={(e) => {
                setPayloadText(e.target.value)
                setPayloadError(null)
              }}
              onBlur={validatePayload}
              rows={14}
              spellCheck={false}
              className={cn(
                'w-full bg-gray-950 border rounded-lg font-mono',
                'px-3 py-3 text-xs text-gray-300 resize-y',
                'focus:outline-none focus:ring-1',
                payloadError
                  ? 'border-red-500 focus:ring-red-500'
                  : 'border-gray-700 focus:ring-forge-500',
              )}
              aria-label="Config payload JSON"
              aria-describedby={payloadError ? 'payload-error' : undefined}
            />
            {payloadError && (
              <p id="payload-error" className="text-xs text-red-400 mt-1">
                {payloadError}
              </p>
            )}
          </div>

          {/* Preview image (optional) */}
          <div>
            <label className="block text-xs font-semibold text-gray-400 mb-1.5" htmlFor="preview">
              Preview image URL <span className="text-gray-600">(optional, HTTPS)</span>
            </label>
            <input
              id="preview"
              type="url"
              value={previewUrl}
              onChange={(e) => setPreviewUrl(e.target.value)}
              placeholder="https://your-cdn.com/screenshot.png"
              className={cn(
                'w-full bg-gray-900 border border-gray-700 rounded-lg',
                'px-3 py-2 text-sm text-gray-200 placeholder-gray-600',
                'focus:outline-none focus:ring-1 focus:ring-forge-500',
              )}
            />
          </div>

          {/* Submit */}
          <div className="flex gap-3 pt-2">
            <button
              type="submit"
              disabled={submitMutation.isPending || !name.trim() || !description.trim()}
              className="flex-1 py-2.5 text-sm font-medium bg-forge-600 hover:bg-forge-500 disabled:opacity-50 text-white rounded-xl transition-colors"
            >
              {submitMutation.isPending ? 'Submitting…' : 'Submit for review'}
            </button>
            <button
              type="button"
              onClick={() => navigate('/marketplace')}
              className="px-5 py-2.5 text-sm text-gray-500 hover:text-gray-300 transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </AppShell>
  )
}
