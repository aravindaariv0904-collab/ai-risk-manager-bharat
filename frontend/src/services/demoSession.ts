/**
 * Demo Session Store
 * ------------------
 * Provides a localStorage-based mock session for demo mode.
 * This bypasses Supabase auth entirely so the app is fully
 * explorable without real credentials.
 */

import type { Profile } from '../types'

const DEMO_SESSION_KEY = 'arm_demo_session'

export interface DemoSession {
  profile: Profile
  token: string // fake JWT for display only
}

export const DEMO_PROFILES: Record<string, Profile> = {
  citizen: {
    id: 'demo-citizen-001',
    auth_user_id: 'demo-auth-citizen',
    name: 'Rahul Kumar',
    phone: '+91 98765 43210',
    role: 'citizen',
    language: 'en',
    created_at: new Date().toISOString(),
  },
  merchant: {
    id: 'demo-merchant-001',
    auth_user_id: 'demo-auth-merchant',
    name: 'Priya Shops',
    phone: '+91 91234 56789',
    role: 'merchant',
    language: 'en',
    created_at: new Date().toISOString(),
  },
  admin: {
    id: 'demo-admin-001',
    auth_user_id: 'demo-auth-admin',
    name: 'Admin User',
    phone: null,
    role: 'admin',
    language: 'en',
    created_at: new Date().toISOString(),
  },
}

export function setDemoSession(role: 'citizen' | 'merchant' | 'admin') {
  const session: DemoSession = {
    profile: DEMO_PROFILES[role],
    token: `demo.${role}.${Date.now()}`,
  }
  localStorage.setItem(DEMO_SESSION_KEY, JSON.stringify(session))
}

export function getDemoSession(): DemoSession | null {
  try {
    const raw = localStorage.getItem(DEMO_SESSION_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function clearDemoSession() {
  localStorage.removeItem(DEMO_SESSION_KEY)
}

export function isDemoMode(): boolean {
  return !!getDemoSession()
}
