import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ShieldCheck, Lock, Mail, User, Eye, EyeOff,
} from 'lucide-react'
import { supabase } from '../services/supabase'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Label } from '../components/ui/Label'
import { Alert } from '../components/ui/Alert'

const FEATURES = [
  { icon: '🔍', text: 'Risk scores before every payment' },
  { icon: '🤖', text: 'AI explanations in English, Hindi & Tamil' },
  { icon: '✅', text: 'Real payment verification for vendors' },
  { icon: '🛡️', text: 'Powered by Razorpay — never a screenshot' },
]

export default function AuthPage() {
  const [mode, setMode] = useState<'login' | 'signup'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [showPass, setShowPass] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      if (mode === 'signup') {
        const { data, error } = await supabase.auth.signUp({
          email,
          password,
          options: { data: { name } },
        })
        if (error) throw error
        if (data.session) await ensureProfile(data.session.user.id, name)
        navigate('/')
      } else {
        const { data, error } = await supabase.auth.signInWithPassword({ email, password })
        if (error) throw error
        if (data.session) await ensureProfile(data.session.user.id)
        navigate('/')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Authentication failed')
    } finally {
      setLoading(false)
    }
  }

  async function ensureProfile(authUserId: string, defaultName?: string) {
    const { data } = await supabase.from('users').select('id').eq('auth_user_id', authUserId).maybeSingle()
    if (!data) {
      await supabase.from('users').insert({
        auth_user_id: authUserId,
        name: defaultName || email.split('@')[0] || 'User',
        role: 'citizen',
        language: 'en',
      })
    }
  }

  return (
    <div className="min-h-screen bg-background flex">
      {/* Left panel — Branding */}
      <div
        className="hidden lg:flex lg:w-[460px] flex-col justify-between p-12 relative overflow-hidden"
        style={{ background: 'linear-gradient(135deg, hsl(243,75%,42%) 0%, hsl(258,75%,55%) 100%)' }}
      >
        <div className="absolute inset-0 opacity-10"
          style={{ backgroundImage: 'radial-gradient(circle, white 1px, transparent 1px)', backgroundSize: '24px 24px' }} />

        <div className="relative z-10">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/20">
              <ShieldCheck className="h-6 w-6 text-white" />
            </div>
            <div>
              <p className="font-bold text-white text-lg leading-tight">AI Risk Manager</p>
              <p className="text-white/70 text-xs">for Bharat's Digital Payments</p>
            </div>
          </div>
        </div>

        <div className="relative z-10 space-y-6">
          <div>
            <h2 className="text-3xl font-bold text-white tracking-tight leading-snug">
              Safe payments for<br />
              <span className="text-white/80">every Indian.</span>
            </h2>
            <p className="text-white/70 text-sm mt-3 max-w-xs">
              AI-powered risk scoring for citizens and micro-merchants — from street vendors to home businesses.
            </p>
          </div>
          <div className="space-y-3">
            {FEATURES.map((f) => (
              <div key={f.text} className="flex items-center gap-3">
                <span className="text-lg">{f.icon}</span>
                <p className="text-sm text-white/85 font-medium">{f.text}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="relative z-10">
          <div className="inline-flex items-center gap-2 rounded-full bg-white/15 border border-white/20 px-4 py-2">
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-300" />
            <span className="text-xs text-white/90 font-semibold">Bank-grade Security · Instant Verification</span>
          </div>
        </div>
      </div>

      {/* Right panel — Auth */}
      <div className="flex-1 flex items-center justify-center p-6 lg:p-10 overflow-y-auto">
        <div className="w-full max-w-md space-y-6 animate-fade-in-up">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
              <ShieldCheck className="h-5 w-5 text-primary" />
            </div>
            <div>
              <p className="font-bold text-foreground">AI Risk Manager for Bharat</p>
              <p className="text-xs text-muted-foreground">Secure Payment Gateway</p>
            </div>
          </div>

          {/* Mode Toggle */}
          <div className="flex rounded-xl bg-muted p-1">
            {(['login', 'signup'] as const).map((m) => (
              <button
                key={m}
                type="button"
                className={`flex-1 rounded-lg py-2.5 text-sm font-semibold transition-all duration-200 ${
                  mode === m ? 'bg-white text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'
                }`}
                onClick={() => { setMode(m); setError(null) }}
              >
                {m === 'login' ? 'Sign In' : 'Register'}
              </button>
            ))}
          </div>

          {error && <Alert variant="error">{error}</Alert>}

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'signup' && (
              <div className="space-y-2">
                <Label htmlFor="name" className="font-semibold text-sm flex items-center gap-2">
                  <User className="h-3.5 w-3.5 text-muted-foreground" />
                  Full Name
                </Label>
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Rahul Kumar"
                  required
                  className="h-11"
                />
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="email" className="font-semibold text-sm flex items-center gap-2">
                <Mail className="h-3.5 w-3.5 text-muted-foreground" />
                Email Address
              </Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                className="h-11"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password" className="font-semibold text-sm flex items-center gap-2">
                <Lock className="h-3.5 w-3.5 text-muted-foreground" />
                Password
              </Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPass ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  minLength={6}
                  className="h-11 pr-10"
                />
                <button
                  type="button"
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  onClick={() => setShowPass(!showPass)}
                  tabIndex={-1}
                >
                  {showPass ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>
            <Button
              type="submit"
              className="w-full h-11 font-semibold btn-primary-gradient"
              loading={loading}
            >
              <ShieldCheck className="h-4 w-4" />
              {mode === 'login' ? 'Sign In Securely' : 'Create Account'}
            </Button>
          </form>

          <p className="text-center text-xs text-muted-foreground pb-4">
            AI Risk Manager for Bharat · Detect · Score · Explain · Verify · Act
          </p>
        </div>
      </div>
    </div>
  )
}