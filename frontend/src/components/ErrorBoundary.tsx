import { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertTriangle } from 'lucide-react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

/**
 * Catches unhandled React render errors and shows a safe fallback
 * instead of a raw stack trace.
 */
export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // In production, pipe this to your error tracking service (Sentry, etc.)
    console.error('[ErrorBoundary]', error, info.componentStack)
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback

      return (
        <div className="min-h-screen bg-gray-950 flex items-center justify-center p-6">
          <div className="max-w-md w-full bg-gray-900 border border-red-900 rounded-2xl p-8 text-center space-y-4">
            <div className="flex justify-center">
              <div className="p-3 rounded-full bg-red-900/30">
                <AlertTriangle size={24} className="text-red-400" />
              </div>
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Something went wrong</h2>
              <p className="text-sm text-gray-400 mt-1">
                An unexpected error occurred. Refresh the page to continue.
              </p>
            </div>
            {process.env.NODE_ENV === 'development' && this.state.error && (
              <pre className="text-left text-xs text-red-400 bg-red-900/20 rounded-lg p-3 overflow-auto max-h-40">
                {this.state.error.message}
              </pre>
            )}
            <button
              onClick={() => window.location.reload()}
              className="inline-flex items-center gap-2 px-4 py-2 bg-forge-600 hover:bg-forge-500 text-white text-sm font-medium rounded-lg transition-colors"
            >
              Reload page
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
