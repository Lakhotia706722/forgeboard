import { type InputHTMLAttributes, forwardRef } from 'react'
import { cn } from '@/lib/utils'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
}

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, id, className, ...props }, ref) => {
    const inputId = id ?? label?.toLowerCase().replace(/\s+/g, '-')

    return (
      <div className="space-y-1">
        {label && (
          <label
            htmlFor={inputId}
            className="block text-sm font-medium text-gray-300"
          >
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          className={cn(
            'w-full rounded-lg border bg-gray-800 px-3 py-2 text-sm text-gray-100',
            'placeholder:text-gray-600',
            'transition-colors duration-150',
            'focus:outline-none focus:ring-2 focus:ring-forge-500 focus:border-forge-500',
            error
              ? 'border-red-500 focus:ring-red-500'
              : 'border-gray-700 hover:border-gray-600',
            'disabled:cursor-not-allowed disabled:opacity-50',
            className,
          )}
          aria-invalid={error ? 'true' : undefined}
          aria-describedby={error ? `${inputId}-error` : undefined}
          {...props}
        />
        {error && (
          <p id={`${inputId}-error`} role="alert" className="text-xs text-red-400">
            {error}
          </p>
        )}
      </div>
    )
  },
)
Input.displayName = 'Input'

export default Input
