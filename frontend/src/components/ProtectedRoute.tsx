import type { ReactNode } from 'react'
import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '../services/supabase'
import { getDemoSession } from '../services/demoSession'

interface ProtectedRouteProps {
  children: ReactNode
}

export default function ProtectedRoute({ children }: ProtectedRouteProps) {
  const navigate = useNavigate()

  useEffect(() => {
    // Demo session bypasses Supabase auth entirely
    if (getDemoSession()) return

    supabase.auth.getSession().then(({ data }) => {
      if (!data.session) {
        navigate('/auth')
      }
    })

    const { data: sub } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!session && !getDemoSession()) navigate('/auth')
    })

    return () => sub.subscription.unsubscribe()
  }, [navigate])

  return <>{children}</>
}