import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center text-gray-100">
      <div className="text-center space-y-4">
        <p className="text-6xl font-bold text-gray-700">404</p>
        <p className="text-xl text-gray-400">Page not found</p>
        <Link to="/dashboard" className="text-forge-400 hover:text-forge-300 text-sm">
          Back to dashboard
        </Link>
      </div>
    </div>
  )
}
