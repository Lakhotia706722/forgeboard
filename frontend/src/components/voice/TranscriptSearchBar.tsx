import { Search, X } from 'lucide-react'
import { cn } from '@/lib/utils'

interface TranscriptSearchBarProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  className?: string
}

export default function TranscriptSearchBar({
  value,
  onChange,
  placeholder = 'Search by number or transcript…',
  className,
}: TranscriptSearchBarProps) {
  return (
    <div className={cn('relative', className)}>
      <Search
        size={14}
        className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none"
        aria-hidden="true"
      />
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={cn(
          'w-full bg-gray-900 border border-gray-700 rounded-lg',
          'pl-9 pr-8 py-2 text-sm text-gray-200 placeholder-gray-600',
          'focus:outline-none focus:ring-1 focus:ring-forge-500 focus:border-forge-500',
          'transition-colors',
        )}
        aria-label="Search call logs"
      />
      {value && (
        <button
          onClick={() => onChange('')}
          className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 transition-colors"
          aria-label="Clear search"
        >
          <X size={13} />
        </button>
      )}
    </div>
  )
}
