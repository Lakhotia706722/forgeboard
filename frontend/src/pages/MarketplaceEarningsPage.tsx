/**
 * MarketplaceEarningsPage — Phase 10d.
 *
 * Author-facing view of install counts and estimated payouts.
 *
 * DISPLAY ONLY — no payment processing is wired.
 * Revenue figures are estimates based on $1.00/install at a 30% platform
 * take rate. Do not present these as actual earned money.
 */
import { useQuery } from '@tanstack/react-query'
import { TrendingUp, Download, DollarSign, Percent, ArrowLeft, AlertTriangle } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import AppShell from '@/components/layout/AppShell'
import { marketplaceApi } from '@/lib/marketplaceApi'
import { cn } from '@/lib/utils'

function StatCard({
  label,
  value,
  sub,
  icon: Icon,
  muted = false,
}: {
  label: string
  value: string | number
  sub?: string
  icon: React.ElementType
  muted?: boolean
}) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-2">
      <div className={cn('flex items-center gap-1.5 text-xs', muted ? 'text-gray-600' : 'text-gray-500')}>
        <Icon size={12} aria-hidden="true" />
        {label}
      </div>
      <p className={cn('text-2xl font-bold', muted ? 'text-gray-500' : 'text-white')}>{value}</p>
      {sub && <p className="text-xs text-gray-600">{sub}</p>}
    </div>
  )
}

export default function MarketplaceEarningsPage() {
  const navigate = useNavigate()

  const { data: stats, isLoading } = useQuery({
    queryKey: ['marketplace-stats'],
    queryFn: marketplaceApi.myStats,
  })

  return (
    <AppShell>
      <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">
        {/* Header */}
        <div>
          <button
            onClick={() => navigate('/marketplace')}
            className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-300 transition-colors mb-4"
          >
            <ArrowLeft size={14} aria-hidden="true" />
            Back to Marketplace
          </button>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <TrendingUp size={18} className="text-forge-400" aria-hidden="true" />
            My Earnings
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Install stats and estimated payouts for your marketplace listings.
          </p>
        </div>

        {/* Disclaimer */}
        <div className="bg-amber-900/20 border border-amber-800 rounded-xl px-4 py-3 flex gap-3">
          <AlertTriangle size={15} className="text-amber-400 flex-shrink-0 mt-0.5" aria-hidden="true" />
          <div className="text-sm text-amber-300 space-y-1">
            <p className="font-medium">Display only — no payments are processed yet.</p>
            <p className="text-xs text-amber-400">
              Figures are estimates based on $1.00 / install at a 30% platform take rate.
              Payment processing (Stripe Connect or manual payout) will be configured once
              marketplace activity justifies it.
            </p>
          </div>
        </div>

        {isLoading && (
          <div className="flex items-center justify-center py-16 text-gray-600">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-gray-700 border-t-forge-500" />
          </div>
        )}

        {stats && (
          <>
            {/* Summary stats */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <StatCard
                label="Approved listings"
                value={stats.listing_count}
                icon={TrendingUp}
              />
              <StatCard
                label="Total installs"
                value={stats.total_installs.toLocaleString()}
                icon={Download}
              />
              <StatCard
                label="Est. payout"
                value={`$${stats.estimated_payout_usd.toFixed(2)}`}
                sub="After platform fee"
                icon={DollarSign}
              />
              <StatCard
                label="Platform take"
                value={`${stats.take_rate_pct}%`}
                sub={`$${stats.platform_take_usd.toFixed(2)} gross`}
                icon={Percent}
                muted
              />
            </div>

            {/* No listings state */}
            {stats.listing_count === 0 && (
              <div className="text-center py-12 text-gray-600">
                <TrendingUp size={32} className="mx-auto mb-3 opacity-30" aria-hidden="true" />
                <p className="text-sm">You don't have any approved listings yet.</p>
                <button
                  onClick={() => navigate('/marketplace/submit')}
                  className="mt-3 text-xs text-forge-400 hover:text-forge-300 transition-colors"
                >
                  Submit your first listing →
                </button>
              </div>
            )}

            {/* Per-listing breakdown */}
            {stats.listings.length > 0 && (
              <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
                <div className="px-4 py-3 border-b border-gray-800">
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    Per-listing breakdown
                  </p>
                </div>
                <table className="w-full text-sm" role="table" aria-label="Earnings per listing">
                  <thead>
                    <tr className="border-b border-gray-800 bg-gray-900/60">
                      {['Listing', 'Installs', 'Est. payout'].map((h) => (
                        <th
                          key={h}
                          className={cn(
                            'px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wider',
                            h === 'Installs' || h === 'Est. payout' ? 'text-right' : 'text-left',
                          )}
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {stats.listings.map((l, i) => (
                      <tr
                        key={l.id}
                        className={cn(
                          'border-b border-gray-800/60 hover:bg-gray-800/20 transition-colors',
                          i === stats.listings.length - 1 && 'border-b-0',
                        )}
                      >
                        <td className="px-4 py-3 text-gray-300 font-medium">{l.name}</td>
                        <td className="px-4 py-3 text-right text-gray-400">
                          {l.install_count.toLocaleString()}
                        </td>
                        <td className="px-4 py-3 text-right text-gray-300 font-mono">
                          ${l.estimated_payout_usd.toFixed(2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Footer note */}
            <p className="text-xs text-gray-700 text-center">{stats.note}</p>
          </>
        )}
      </div>
    </AppShell>
  )
}
