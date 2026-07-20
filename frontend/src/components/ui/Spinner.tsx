import { cn } from '@/lib/utils'

interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  className?: string
  label?: string
}

const SIZE = { sm: 'h-4 w-4', md: 'h-6 w-6', lg: 'h-8 w-8' }

export default function Spinner({ size = 'md', className, label = 'Loading…' }: SpinnerProps) {
  return (
    <div role="status" aria-label={label} className={cn('inline-flex', className)}>
      <div
        className={cn(
          'animate-spin rounded-full border-2 border-gray-700 border-t-forge-500',
          SIZE[size],
        )}
      />
      <span className="sr-only">{label}</span>
    </div>
  )
}
