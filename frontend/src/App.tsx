import { useEffect, useState } from 'react'
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import {
  ShieldCheck,
  LayoutDashboard,
  Send,
  History,
  Bot,
  Store,
  ShieldAlert,
  Settings,
  LogOut,
  Zap,
  Menu,
  X,
} from 'lucide-react'
import { supabase } from './services/supabase'
import { getDemoSession, clearDemoSession } from './services/demoSession'
import type { Profile } from './types'
import { cn } from './lib/utils'

const NAV_LINKS_CITIZEN = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, exact: true },
  { to: '/pay', label: 'New Payment', icon: Send, exact: false },
  { to: '/history', label: 'Transactions', icon: History, exact: false },
  { to: '/assistant', label: 'AI Assistant', icon: Bot, exact: false },
]

const NAV_LINKS_VENDOR = [
  { to: '/vendor', label: 'Dashboard', icon: Store, exact: true },
  { to: '/vendor/verify', label: 'Verify Payment', icon: ShieldCheck, exact: false },
  { to: '/vendor/transactions', label: 'Transactions', icon: History, exact: false },
]

function isActive(pathname: string, to: string, exact: boolean) {
  if (exact) return pathname === to
  return pathname.startsWith(to)
}

export default function App() {
  const [profile, setProfile] = useState<Profile | null>(null)
  const [loading, setLoading] = useState(true)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()

  useEffect(() => {
    setMobileMenuOpen(false)
  }, [location.pathname])

  useEffect(() => {
    async function loadProfile() {
      // Check demo session first
      const demo = getDemoSession()
      if (demo) {
        setProfile(demo.profile)
        setLoading(false)
        return
      }

      const { data: { session } } = await supabase.auth.getSession()
      if (!session) {
        setLoading(false)
        return
      }

      const { data } = await supabase
        .from('users')
        .select('*')
        .eq('auth_user_id', session.user.id)
        .maybeSingle()

      if (data) {
        setProfile(data as Profile)
        setLoading(false)
        return
      }

      // Auto-create profile if missing
      const user = session.user
      const { error } = await supabase.from('users').insert({
        auth_user_id: user.id,
        name: user.user_metadata?.full_name || user.email?.split('@')[0] || 'User',
        role: 'citizen',
        language: 'en',
      })

      if (!error) {
        const { data: retry } = await supabase
          .from('users')
          .select('*')
          .eq('auth_user_id', session.user.id)
          .maybeSingle()
        if (retry) setProfile(retry as Profile)
      }
      setLoading(false)
    }
    loadProfile()
  }, [])

  async function handleLogout() {
    clearDemoSession()
    await supabase.auth.signOut()
    setProfile(null)
    navigate('/auth')
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4 animate-fade-in">
          <div className="relative">
            <div className="h-16 w-16 rounded-2xl bg-primary/10 flex items-center justify-center animate-pulse-ring">
              <ShieldCheck className="h-8 w-8 text-primary" />
            </div>
          </div>
          <div className="text-center">
            <p className="font-semibold text-foreground">AI Risk Manager</p>
            <p className="text-sm text-muted-foreground mt-0.5">Loading your secure dashboard...</p>
          </div>
        </div>
      </div>
    )
  }

  const links = profile?.role === 'merchant' ? NAV_LINKS_VENDOR : NAV_LINKS_CITIZEN

  return (
    <div className="min-h-screen bg-background">
      {/* Glassmorphic Navigation */}
      <header className="sticky top-0 z-40 nav-glass">
        <div className="flex h-16 items-center justify-between px-4 lg:px-8 max-w-7xl mx-auto">
          {/* Brand */}
          <Link to={profile?.role === 'merchant' ? '/vendor' : '/'} className="flex items-center gap-3 group">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 group-hover:bg-primary/15 transition-colors">
              <ShieldCheck className="h-5 w-5 text-primary" />
            </div>
            <div>
              <p className="font-bold text-sm leading-tight gradient-text">AI Risk Manager</p>
              <p className="text-[10px] text-muted-foreground leading-tight font-medium">for Bharat</p>
            </div>
          </Link>

          {/* Desktop Nav */}
          <nav className="hidden md:flex items-center gap-1">
            {links.map((link) => {
              const active = isActive(location.pathname, link.to, link.exact)
              return (
                <Link
                  key={link.to}
                  to={link.to}
                  className={cn(
                    'inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition-all duration-150',
                    active
                      ? 'bg-primary/10 text-primary shadow-sm'
                      : 'text-muted-foreground hover:bg-accent hover:text-foreground',
                  )}
                >
                  <link.icon className="h-4 w-4" />
                  {link.label}
                </Link>
              )
            })}
          </nav>

          {/* Right Actions */}
          <div className="flex items-center gap-2">
            {profile?.role === 'admin' && (
              <Link
                to="/admin"
                className={cn(
                  'hidden md:inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-all',
                  location.pathname.startsWith('/admin')
                    ? 'bg-amber-100 text-amber-700'
                    : 'text-muted-foreground hover:bg-accent',
                )}
              >
                <ShieldAlert className="h-4 w-4" />
                Admin
              </Link>
            )}

            {/* Role badge */}
            {profile && (
              <span className={cn(
                'hidden sm:inline-flex rounded-full px-2.5 py-1 text-xs font-semibold capitalize',
                profile.role === 'merchant'
                  ? 'bg-emerald-100 text-emerald-700'
                  : profile.role === 'admin'
                  ? 'bg-amber-100 text-amber-700'
                  : 'bg-primary/10 text-primary',
              )}>
                {profile.role}
              </span>
            )}

            <Link
              to="/settings"
              className="inline-flex items-center rounded-lg p-2 text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
              title="Settings"
            >
              <Settings className="h-4 w-4" />
            </Link>
            <button
              onClick={handleLogout}
              className="inline-flex items-center rounded-lg p-2 text-muted-foreground hover:bg-red-50 hover:text-red-600 transition-colors"
              title="Sign out"
            >
              <LogOut className="h-4 w-4" />
            </button>

            {/* Mobile menu toggle */}
            <button
              className="md:hidden inline-flex items-center rounded-lg p-2 text-muted-foreground hover:bg-accent"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            >
              {mobileMenuOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
            </button>
          </div>
        </div>

        {/* Mobile Nav Dropdown */}
        {mobileMenuOpen && (
          <div className="md:hidden border-t bg-white/98 px-4 py-3 space-y-1 animate-fade-in-up shadow-lg">
            {links.map((link) => {
              const active = isActive(location.pathname, link.to, link.exact)
              return (
                <Link
                  key={link.to}
                  to={link.to}
                  className={cn(
                    'flex items-center gap-3 rounded-lg px-4 py-3 text-sm font-medium transition-colors',
                    active
                      ? 'bg-primary/10 text-primary'
                      : 'text-muted-foreground hover:bg-accent hover:text-foreground',
                  )}
                >
                  <link.icon className="h-4 w-4" />
                  {link.label}
                </Link>
              )
            })}
            {profile?.role === 'admin' && (
              <Link
                to="/admin"
                className="flex items-center gap-3 rounded-lg px-4 py-3 text-sm font-medium text-amber-700 hover:bg-amber-50"
              >
                <ShieldAlert className="h-4 w-4" />
                Admin Dashboard
              </Link>
            )}
          </div>
        )}
      </header>

      {/* Page Content */}
      <main className="mx-auto max-w-7xl px-4 py-8 lg:px-8">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="border-t bg-white/60 backdrop-blur-sm py-6 mt-12">
        <div className="max-w-7xl mx-auto px-4 lg:px-8">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-primary" />
              <span className="text-sm font-semibold gradient-text">AI Risk Manager for Bharat</span>
            </div>
            <p className="text-xs text-muted-foreground text-center">
              AI-powered payment risk management · Real-time protection for everyday transactions
            </p>
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <span>Detect · Score · Explain · Verify · Act · Learn</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}