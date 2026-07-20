import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface EmptyStateProps {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
  className?: string
}

export default function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center py-16 text-center gap-4',
        className,
      )}
    >
      {icon && (
        <div className="p-4 rounded-2xl bg-gray-900 border border-gray-800 text-gray-600">
          {icon}
        </div>
      )}
      <div className="space-y-1">
        <p className="font-medium text-gray-300">{title}</p>
        {description && (
          <p className="text-sm text-gray-600 max-w-xs mx-auto">{description}</p>
        )}
      </div>
      {action && <div>{action}</div>}
    </div>
  )
}
