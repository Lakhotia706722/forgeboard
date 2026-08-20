import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Download, Package, Cpu, Plug, Tag, Hash } from 'lucide-react'
import toast from 'react-hot-toast'

import AppShell from '@/components/layout/AppShell'
import { marketplaceApi } from '@/lib/marketplaceApi'
import { useAuthStore } from '@/store/authStore'
import { cn } from '@/lib/utils'

// Human-readable connector type names
const CONNECTOR_LABELS: Record<string, string> = {
  google_calendar: 'Google Calendar',
  gmail: 'Gmail',
  http_webhook: 'HTTP / Webhook',
  kv_store: 'Notes Store (KV)',
}

function ConnectorBadge({ type }: { type: string }) {
  return (
    <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-gray-800 border border-gray-700 text-xs text-gray-300">
      <Plug size={10} aria-hidden="true" className="text-gray-500" />
      {CONNECTOR_LABELS[type] ?? type}
    </span>
  )
}

export default function MarketplaceListingPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const activeWorkspace = useAuthStore((s) => s.activeWorkspace)()

  const { data: listing, isLoading } = useQuery({
    queryKey: ['marketplace-listing', id],
    queryFn: () => marketplaceApi.getListing(id!),
    enabled: !!id,
  })

  const installMutation = useMutation({
    mutationFn: () => marketplaceApi.install(id!),
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ['agents'] })
      qc.invalidateQueries({ queryKey: ['connectors'] })
      qc.invalidateQueries({ queryKey: ['marketplace'] })
      const target = result.installed_type === 'agent' ? '/board' : '/connectors'
      toast.success(
        `"${result.listing_name}" installed! ${
          result.installed_type === 'agent'
            ? 'Find it in Draft on the board.'
            : 'Find it in Connectors — connect your account to activate.'
        }`,
      )
      navigate(target)
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Install failed.'),
  })

  const requiredConnectors: string[] =
    (listing?.config_payload?.required_connector_types as string[]) ?? []

  return (
    <AppShell>
      <div className="max-w-3xl mx-auto px-6 py-8">
        {/* Back */}
        <button
          onClick={() => navigate('/marketplace')}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-300 transition-colors mb-6"
        >
          <ArrowLeft size={14} aria-hidden="true" />
          Back to Marketplace
        </button>

        {isLoading && (
          <div className="flex items-center justify-center py-20 text-gray-600">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-gray-700 border-t-forge-500" role="status" />
          </div>
        )}

        {listing && (
          <div className="space-y-6">
            {/* Header */}
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    {listing.listing_type === 'agent' ? (
                      <Cpu size={16} className="text-forge-400 flex-shrink-0" aria-hidden="true" />
                    ) : (
                      <Plug size={16} className="text-forge-400 flex-shrink-0" aria-hidden="true" />
                    )}
                    <span className="text-xs text-gray-500 capitalize">{listing.listing_type} template</span>
                    <span className="text-gray-700">·</span>
                    <span className="text-xs text-gray-600">{listing.category}</span>
                    <span className="text-gray-700">·</span>
                    <span className="text-xs text-gray-600">v{listing.version}</span>
                  </div>
                  <h1 className="text-xl font-bold text-white">{listing.name}</h1>
                  <p className="text-sm text-gray-500 mt-0.5">
                    by <span className="text-gray-400">{listing.author_name}</span>
                  </p>
                </div>

                <div className="flex flex-col items-end gap-2 flex-shrink-0">
                  <button
                    onClick={() => {
                      if (!activeWorkspace) {
                        toast.error('Select a workspace first.')
                        return
                      }
                      installMutation.mutate()
                    }}
                    disabled={installMutation.isPending}
                    className={cn(
                      'flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium',
                      'bg-forge-600 hover:bg-forge-500 text-white disabled:opacity-50 transition-colors',
                    )}
                    aria-label={`Install ${listing.name}`}
                  >
                    <Download size={14} aria-hidden="true" />
                    {installMutation.isPending ? 'Installing…' : 'Install'}
                  </button>
                  <span className="text-xs text-gray-600">
                    {listing.install_count.toLocaleString()} installs
                  </span>
                </div>
              </div>

              <p className="text-sm text-gray-300 leading-relaxed mt-4">
                {listing.description}
              </p>
            </div>

            {/* What you get */}
            <section className="bg-gray-900 border border-gray-800 rounded-2xl p-5 space-y-3">
              <h2 className="text-sm font-semibold text-white">What gets installed</h2>
              <ul className="text-sm text-gray-400 space-y-1.5">
                {listing.listing_type === 'agent' && (
                  <>
                    <li className="flex items-start gap-2">
                      <span className="text-green-400 mt-0.5 flex-shrink-0">✓</span>
                      A new agent in <strong className="text-gray-300">Draft</strong> status on your board
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="text-green-400 mt-0.5 flex-shrink-0">✓</span>
                      Pre-filled goal and trigger configuration
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="text-yellow-400 mt-0.5 flex-shrink-0">→</span>
                      You'll need to link your own connectors before the agent can run
                    </li>
                  </>
                )}
                {listing.listing_type === 'connector' && (
                  <>
                    <li className="flex items-start gap-2">
                      <span className="text-green-400 mt-0.5 flex-shrink-0">✓</span>
                      A pre-configured connector record in your workspace
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="text-yellow-400 mt-0.5 flex-shrink-0">→</span>
                      You'll need to authenticate (OAuth or API key) to activate it
                    </li>
                  </>
                )}
                <li className="flex items-start gap-2">
                  <span className="text-gray-500 mt-0.5 flex-shrink-0">✗</span>
                  <span className="text-gray-600">Run history, costs, and credentials are never transferred</span>
                </li>
              </ul>
            </section>

            {/* Required connectors */}
            {requiredConnectors.length > 0 && (
              <section className="bg-gray-900 border border-gray-800 rounded-2xl p-5 space-y-3">
                <h2 className="text-sm font-semibold text-white flex items-center gap-2">
                  Required connectors
                </h2>
                <p className="text-xs text-gray-500">
                  This agent needs these connector types. You can link them after installing.
                </p>
                <div className="flex flex-wrap gap-2">
                  {requiredConnectors.map((ct) => (
                    <ConnectorBadge key={ct} type={ct} />
                  ))}
                </div>
              </section>
            )}

            {/* Config preview */}
            <section className="bg-gray-900 border border-gray-800 rounded-2xl p-5 space-y-3">
              <h2 className="text-sm font-semibold text-white">Template config</h2>
              <p className="text-xs text-gray-500">
                Read-only preview of what this template installs. Editing happens after install.
              </p>
              <pre className="bg-gray-950 border border-gray-800 rounded-lg p-4 text-xs text-gray-400 overflow-x-auto leading-relaxed whitespace-pre-wrap">
                {JSON.stringify(listing.config_payload, null, 2)}
              </pre>
            </section>

            {/* Install CTA bottom */}
            {!activeWorkspace && (
              <div className="bg-amber-900/20 border border-amber-800 rounded-xl px-4 py-3 text-sm text-amber-300">
                Select a workspace from the top nav to install this listing.
              </div>
            )}
          </div>
        )}
      </div>
    </AppShell>
  )
}
