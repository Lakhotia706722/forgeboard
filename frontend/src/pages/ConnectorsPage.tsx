import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Plug } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import toast from 'react-hot-toast'

import { connectorApi, type ConnectorOut } from '@/lib/connectorApi'
import Button from '@/components/ui/Button'
import ConnectorCard from '@/components/connectors/ConnectorCard'
import AddConnectorModal from '@/components/connectors/AddConnectorModal'

export default function ConnectorsPage() {
  const queryClient = useQueryClient()
  const [showModal, setShowModal] = useState(false)
  const [searchParams] = useSearchParams()

  // Show a toast if returning from Google OAuth
  const connectedParam = searchParams.get('connected')
  const errorParam = searchParams.get('error')
  if (connectedParam === 'google') {
    toast.success('Google account connected!', { id: 'google-connected' })
  }
  if (errorParam) {
    toast.error(`OAuth error: ${errorParam}`, { id: 'oauth-error' })
  }

  const {
    data: connectors = [],
    isLoading,
    isError,
  } = useQuery({
    queryKey: ['connectors'],
    queryFn: connectorApi.list,
  })

  function handleDeleted(id: string) {
    queryClient.setQueryData<ConnectorOut[]>(['connectors'], (prev) =>
      (prev ?? []).filter((c) => c.id !== id),
    )
  }

  function handleUpdated(updated: ConnectorOut) {
    queryClient.setQueryData<ConnectorOut[]>(['connectors'], (prev) =>
      (prev ?? []).map((c) => (c.id === updated.id ? updated : c)),
    )
  }

  function handleAdded(connector: ConnectorOut) {
    queryClient.setQueryData<ConnectorOut[]>(['connectors'], (prev) => [
      ...(prev ?? []),
      connector,
    ])
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-10">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Connectors</h1>
          <p className="mt-1 text-sm text-gray-400">
            Connect your tools to power your agents.
          </p>
        </div>
        <Button onClick={() => setShowModal(true)}>
          <Plus size={15} aria-hidden="true" />
          Add connector
        </Button>
      </div>

      {/* States */}
      {isLoading && (
        <div className="flex items-center justify-center py-20 text-gray-600">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-700 border-t-forge-500 mr-3" />
          Loading connectors…
        </div>
      )}

      {isError && (
        <div className="rounded-xl bg-red-900/20 border border-red-800 px-6 py-4 text-red-300 text-sm">
          Failed to load connectors. Please refresh.
        </div>
      )}

      {!isLoading && !isError && connectors.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center gap-4">
          <div className="p-4 rounded-2xl bg-gray-900 border border-gray-800">
            <Plug size={28} className="text-gray-600" />
          </div>
          <div>
            <p className="font-medium text-gray-300">No connectors yet</p>
            <p className="text-sm text-gray-600 mt-1">
              Add your first connector to start building agents.
            </p>
          </div>
          <Button onClick={() => setShowModal(true)}>
            <Plus size={15} />
            Add connector
          </Button>
        </div>
      )}

      {!isLoading && connectors.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {connectors.map((connector) => (
            <ConnectorCard
              key={connector.id}
              connector={connector}
              onDeleted={handleDeleted}
              onUpdated={handleUpdated}
            />
          ))}
        </div>
      )}

      {showModal && (
        <AddConnectorModal
          onClose={() => setShowModal(false)}
          onAdded={handleAdded}
        />
      )}
    </div>
  )
}
