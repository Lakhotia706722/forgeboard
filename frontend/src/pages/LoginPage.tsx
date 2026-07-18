import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'

import { authApi } from '@/lib/authApi'
import { useAuthStore } from '@/store/authStore'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'

export default function LoginPage() {
  const navigate = useNavigate()
  const setAuth = useAuthStore((s) => s.setAuth)

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [errors, setErrors] = useState<{ email?: string; password?: string; form?: string }>({})

  function validate(): boolean {
    const next: typeof errors = {}
    if (!email) next.email = 'Email is required.'
    if (!password) next.password = 'Password is required.'
    setErrors(next)
    return Object.keys(next).length === 0
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!validate()) return

    setLoading(true)
    setErrors({})

    try {
      const { tokens, user } = await authApi.login({ email, password })
      setAuth(tokens.access_token, tokens.refresh_token, user)
      toast.success(`Welcome back, ${user.full_name.split(' ')[0]}!`)
      navigate('/dashboard')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed.'
      setErrors({ form: message })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950 px-4">
      <div className="w-full max-w-md space-y-6 p-8 bg-gray-900 rounded-2xl border border-gray-800 shadow-xl">
        <div>
          <h1 className="text-2xl font-bold text-white">Sign in to ForgeBoard</h1>
          <p className="mt-1 text-sm text-gray-400">Welcome back — let's build something.</p>
        </div>

        <form onSubmit={handleSubmit} noValidate className="space-y-4">
          {errors.form && (
            <div
              role="alert"
              className="rounded-lg bg-red-900/30 border border-red-700 px-4 py-3 text-sm text-red-300"
            >
              {errors.form}
            </div>
          )}

          <Input
            label="Email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            error={errors.email}
            placeholder="you@example.com"
          />

          <Input
            label="Password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={errors.password}
            placeholder="••••••••"
          />

          <Button type="submit" loading={loading} className="w-full" size="lg">
            Sign in
          </Button>
        </form>

        <p className="text-center text-sm text-gray-500">
          Don't have an account?{' '}
          <Link to="/signup" className="text-forge-400 hover:text-forge-300 font-medium">
            Sign up
          </Link>
        </p>
      </div>
    </div>
  )
}
