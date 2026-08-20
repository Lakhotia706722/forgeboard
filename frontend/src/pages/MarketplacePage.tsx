import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Store, Download, Search, Star, Clock, Zap, Calendar, Bell, Package } from 'lucide-react'
import toast from 'react-hot-toast'
import { useNavigate, Link } from 'react-router-dom'

import AppShell from '@/components/layout/AppShell'
import { marketplaceApi, type ListingOut, type ListingType } from '@/lib/marketplaceApi'
import { useAuthStore } from '@/store/authStore'
import { cn } from '@/lib/utils'

// ---------------------------------------------------------------------------
// Category icon map
// ---------------------------------------------------------------------------
const CATEGORY_ICONS: Record<string, React.ElementType> = {
  Productivity: Zap,
  Calendar:     Calendar,
  Notifications: Bell,
}

function CategoryIcon({ category }: { category: string }) {
  const Icon = CATEGORY_ICONS[category] ?? Package
  return <Icon size={13} aria-hidden="true" />
}

// ---------------------------------------------------------------------------
// Listing card
// ---------------------------------------------------------------------------
interface ListingCardProps {
  listing: ListingOut
  onInstall: (id: string) => void
  installing: boolean
}

function ListingCard({ listing, onInstall, installing }: ListingCardProps) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 flex flex-col gap-3 hover:border-gray-700 transition-colors">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <Link
            to={`/marketplace/${listing.id}`}
            className="font-semibold text-white text-sm leading-tight truncate hover:text-forge-300 transition-colors block"
            onClick={(e) => e.stopPropagation()}
          >
            {listing.name}
          </Link>
          <div className="flex items-center gap-2 mt-1">
            <span className="flex items-center gap-1 text-xs text-gray-500">
              <CategoryIcon category={listing.category} />
              {listing.category}
            </span>
            <span className="text-gray-700">·</span>
            <span className="text-xs text-gray-600 capitalize">{listing.listing_type}</span>
          </div>
        </div>
        <span className="flex items-center gap-1 text-xs text-gray-600 flex-shrink-0">
          <Download size={10} aria-hidden="true" />
          {listing.install_count.toLocaleString()}
        </span>
      </div>

      {/* Description */}
      <p className="text-xs text-gray-400 leading-relaxed line-clamp-3 flex-1">
        {listing.description}
      </p>

      {/* Footer */}
      <div className="flex items-center justify-between pt-1 border-t border-gray-800">
        <span className="text-xs text-gray-600">
          by <span className="text-gray-500">{listing.author_name}</span>
        </span>
        <button
          onClick={() => onInstall(listing.id)}
          disabled={installing}
          className={cn(
            'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
            'bg-forge-600 hover:bg-forge-500 text-white disabled:opacity-50',
          )}
          aria-label={`Install ${listing.name}`}
        >
          <Download size={11} aria-hidden="true" />
          {installing ? 'Installing…' : 'Install'}
        </button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function MarketplacePage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const activeWorkspace = useAuthStore((s) => s.activeWorkspace)()
  const user = useAuthStore((s) => s.user)
  const myRole = activeWorkspace?.role

  const [search, setSearch] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [selectedType, setSelectedType] = useState<ListingType | null>(null)
  const [sort, setSort] = useState<'popular' | 'recent'>('popular')
  const [installingId, setInstallingId] = useState<string | null>(null)

  const { data: categories = [] } = useQuery({
    queryKey: ['marketplace-categories'],
    queryFn: marketplaceApi.listCategories,
  })

  const { data: listings = [], isLoading } = useQuery({
    queryKey: ['marketplace', search, selectedCategory, selectedType, sort],
    queryFn: () =>
      marketplaceApi.listCatalog({
        q: search || undefined,
        category: selectedCategory ?? undefined,
        listing_type: selectedType ?? undefined,
        sort,
        limit: 50,
      }),
  })

  const installMutation = useMutation({
    mutationFn: (listingId: string) => marketplaceApi.install(listingId),
    onMutate: (id) => setInstallingId(id),
    onSuccess: (result) => {
      setInstallingId(null)
      qc.invalidateQueries({ queryKey: ['agents'] })
      qc.invalidateQueries({ queryKey: ['connectors'] })

      const target = result.installed_type === 'agent' ? '/board' : '/connectors'
      toast.success(
        `"${result.listing_name}" installed! ${
          result.installed_type === 'agent'
            ? 'Find it in Draft on your agent board.'
            : 'Find it in Connectors — you\'ll need to authenticate.'
        }`,
      )
      navigate(target)
    },
    onError: (e) => {
      setInstallingId(null)
      toast.error(e instanceof Error ? e.message : 'Install failed.')
    },
  })

  return (
    <AppShell>
      <div className="max-w-6xl mx-auto px-6 py-8 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-white flex items-center gap-2">
              <Store size={18} className="text-forge-400" aria-hidden="true" />
              Marketplace
            </h1>
            <p className="text-sm text-gray-500 mt-0.5">
              Ready-made agent and connector templates — install into your workspace in one click.
            </p>
          </div>
          <button
            onClick={() => navigate('/marketplace/submit')}
            className="text-xs text-gray-500 hover:text-gray-300 border border-gray-700 hover:border-gray-500 px-3 py-1.5 rounded-lg transition-colors"
          >
            Submit a listing
          </button>
          <button
            onClick={() => navigate('/marketplace/earnings')}
            className="text-xs text-gray-500 hover:text-gray-300 border border-gray-700 hover:border-gray-500 px-3 py-1.5 rounded-lg transition-colors"
          >
            My earnings
          </button>
          {(myRole === 'owner' || myRole === 'admin') && (
            <button
              onClick={() => navigate('/marketplace/admin')}
              className="text-xs text-gray-500 hover:text-gray-300 border border-gray-700 hover:border-gray-500 px-3 py-1.5 rounded-lg transition-colors"
            >
              Review queue
            </button>
          )}
        </div>

        {/* No active workspace warning */}
        {!activeWorkspace && (
          <div className="bg-amber-900/20 border border-amber-800 rounded-xl px-4 py-3 text-sm text-amber-300">
            Select a workspace to install listings.
          </div>
        )}

        {/* Search + filters */}
        <div className="flex flex-wrap gap-3 items-center">
          {/* Search */}
          <div className="relative flex-1 min-w-[200px] max-w-sm">
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" aria-hidden="true" />
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search listings…"
              className={cn(
                'w-full bg-gray-900 border border-gray-700 rounded-lg',
                'pl-8 pr-3 py-2 text-sm text-gray-200 placeholder-gray-600',
                'focus:outline-none focus:ring-1 focus:ring-forge-500',
              )}
              aria-label="Search marketplace listings"
            />
          </div>

          {/* Category filter */}
          <div className="flex items-center gap-1.5 flex-wrap">
            <button
              onClick={() => setSelectedCategory(null)}
              className={cn(
                'px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
                selectedCategory === null
                  ? 'bg-forge-600 text-white'
                  : 'bg-gray-800 text-gray-400 hover:text-gray-200',
              )}
            >
              All
            </button>
            {categories.map((cat) => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat === selectedCategory ? null : cat)}
                className={cn(
                  'flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
                  selectedCategory === cat
                    ? 'bg-forge-600 text-white'
                    : 'bg-gray-800 text-gray-400 hover:text-gray-200',
                )}
              >
                <CategoryIcon category={cat} />
                {cat}
              </button>
            ))}
          </div>

          {/* Type filter */}
          <div className="flex items-center gap-1.5 ml-auto">
            <button
              onClick={() => setSelectedType(null)}
              className={cn(
                'px-2.5 py-1.5 rounded-lg text-xs transition-colors',
                selectedType === null ? 'bg-gray-700 text-white' : 'text-gray-500 hover:text-gray-300',
              )}
            >
              All types
            </button>
            {(['agent', 'connector'] as ListingType[]).map((t) => (
              <button
                key={t}
                onClick={() => setSelectedType(selectedType === t ? null : t)}
                className={cn(
                  'px-2.5 py-1.5 rounded-lg text-xs capitalize transition-colors',
                  selectedType === t ? 'bg-gray-700 text-white' : 'text-gray-500 hover:text-gray-300',
                )}
              >
                {t}s
              </button>
            ))}

            {/* Sort */}
            <div className="w-px h-4 bg-gray-700 mx-1" aria-hidden="true" />
            <button
              onClick={() => setSort('popular')}
              className={cn(
                'flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs transition-colors',
                sort === 'popular' ? 'bg-gray-700 text-white' : 'text-gray-500 hover:text-gray-300',
              )}
              aria-label="Sort by popularity"
            >
              <Star size={10} aria-hidden="true" /> Popular
            </button>
            <button
              onClick={() => setSort('recent')}
              className={cn(
                'flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs transition-colors',
                sort === 'recent' ? 'bg-gray-700 text-white' : 'text-gray-500 hover:text-gray-300',
              )}
              aria-label="Sort by recency"
            >
              <Clock size={10} aria-hidden="true" /> Recent
            </button>
          </div>
        </div>

        {/* Results */}
        {isLoading && (
          <div className="flex items-center justify-center py-20 text-gray-600">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-gray-700 border-t-forge-500" role="status" aria-label="Loading" />
          </div>
        )}

        {!isLoading && listings.length === 0 && (
          <div className="text-center py-20 text-gray-600">
            <Store size={32} className="mx-auto mb-3 opacity-30" aria-hidden="true" />
            <p className="text-sm">No listings match your search.</p>
          </div>
        )}

        {!isLoading && listings.length > 0 && (
          <>
            <p className="text-xs text-gray-600">
              {listings.length} listing{listings.length !== 1 ? 's' : ''}
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {listings.map((listing) => (
                <ListingCard
                  key={listing.id}
                  listing={listing}
                  onInstall={(id) => {
                    if (!activeWorkspace) {
                      toast.error('Select a workspace first.')
                      return
                    }
                    installMutation.mutate(id)
                  }}
                  installing={installingId === listing.id}
                />
              ))}
            </div>
          </>
        )}
      </div>
    </AppShell>
  )
}
