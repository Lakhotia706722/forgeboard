import { AlertCircle, RefreshCw } from 'lucide-react'

interface PageErrorProps {
  message?: string
  onRetry?: () => void
}

export default function PageError({
  message = 'Failed to load data.',
  onRetry,
}: PageErrorProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-4 text-center">
      <div className="p-3 rounded-full bg-red-900/20">
        <AlertCircle size={20} className="text-red-400" />
      </div>
      <div>
        <p className="text-sm font-medium text-gray-300">Something went wrong</p>
        <p className="text-xs text-gray-500 mt-1">{message}</p>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center gap-1.5 text-xs text-forge-400 hover:text-forge-300 transition-colors"
        >
          <RefreshCw size={12} /> Retry
        </button>
      )}
    </div>
  )
}
