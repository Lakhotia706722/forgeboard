import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'

import LoginPage from '@/pages/LoginPage'
import SignupPage from '@/pages/SignupPage'
import DashboardPage from '@/pages/DashboardPage'
import BoardPage from '@/pages/BoardPage'
import ConnectorsPage from '@/pages/ConnectorsPage'
import GovernancePage from '@/pages/GovernancePage'
import VoicePage from '@/pages/VoicePage'
import WorkspaceSettingsPage from '@/pages/WorkspaceSettingsPage'
import AgencyDashboardPage from '@/pages/AgencyDashboardPage'
import MarketplacePage from '@/pages/MarketplacePage'
import NotFoundPage from '@/pages/NotFoundPage'
import ProtectedRoute from '@/components/ProtectedRoute'
import GuestRoute from '@/components/GuestRoute'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Guest-only */}
        <Route element={<GuestRoute />}>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />
        </Route>

        {/* Protected */}
        <Route element={<ProtectedRoute />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/board" element={<BoardPage />} />
          <Route path="/connectors" element={<ConnectorsPage />} />
          <Route path="/governance" element={<GovernancePage />} />
          <Route path="/voice" element={<VoicePage />} />
          <Route path="/settings" element={<WorkspaceSettingsPage />} />
          <Route path="/agency" element={<AgencyDashboardPage />} />
          <Route path="/marketplace" element={<MarketplacePage />} />
        </Route>

        {/* Redirects */}
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  )
}
