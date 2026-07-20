import { useState } from 'react'
import { Link } from 'react-router-dom'
import { X, ArrowRight, Plug, Cpu, Zap } from 'lucide-react'

const STORAGE_KEY = 'forgeboard-onboarding-dismissed'

const STEPS = [
  {
    icon: Plug,
    title: 'Connect your tools',
    description: 'Start with the Notes Store — no OAuth needed.',
    href: '/connectors',
    cta: 'Add a connector',
  },
  {
    icon: Cpu,
    title: 'Describe an agent',
    description: 'Tell it what to do in plain language.',
    href: '/board',
    cta: 'Build an agent',
  },
  {
    icon: Zap,
    title: 'Run it',
    description: 'Hit "Run now" to see it execute live.',
    href: '/board',
    cta: 'Open the board',
  },
]

export default function OnboardingBanner() {
  const [dismissed, setDismissed] = useState(
    () => localStorage.getItem(STORAGE_KEY) === 'true',
  )

  function dismiss() {
    localStorage.setItem(STORAGE_KEY, 'true')
    setDismissed(true)
  }

  if (dismissed) return null

  return (
    <div className="relative bg-gradient-to-r from-forge-900/60 to-gray-900 border border-forge-800 rounded-xl p-5 mb-6">
      {/* Dismiss */}
      <button
        onClick={dismiss}
        className="absolute top-3 right-3 text-gray-600 hover:text-gray-300 transition-colors"
        aria-label="Dismiss getting started guide"
      >
        <X size={16} />
      </button>

      <p className="text-xs font-semibold text-forge-400 uppercase tracking-wider mb-3">
        Getting started
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {STEPS.map((step, i) => {
          const Icon = step.icon
          return (
            <div
              key={step.title}
              className="flex items-start gap-3 bg-gray-900/60 rounded-xl p-3 border border-gray-800"
            >
              <div className="flex-shrink-0 flex items-center justify-center h-7 w-7 rounded-full bg-forge-800 text-forge-300 text-xs font-bold">
                {i + 1}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5 mb-0.5">
                  <Icon size={13} className="text-forge-400 flex-shrink-0" />
                  <p className="text-sm font-medium text-white">{step.title}</p>
                </div>
                <p className="text-xs text-gray-500">{step.description}</p>
                <Link
                  to={step.href}
                  className="inline-flex items-center gap-1 mt-2 text-xs text-forge-400 hover:text-forge-300 transition-colors"
                >
                  {step.cta} <ArrowRight size={11} />
                </Link>
              </div>
            </div>
          )
        })}
      </div>

      <button
        onClick={dismiss}
        className="mt-3 text-xs text-gray-600 hover:text-gray-400 transition-colors"
      >
        Dismiss
      </button>
    </div>
  )
}
