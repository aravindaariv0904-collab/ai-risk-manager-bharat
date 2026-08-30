import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Wallet, ShieldCheck, Clock, TriangleAlert, ArrowRight, TrendingUp, Sparkles,
} from 'lucide-react'
import { vendorApi } from '../features/vendor/vendorService'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Alert } from '../components/ui/Alert'
import { Skeleton } from '../components/ui/Skeleton'
import RiskLevelBadge from '../components/RiskLevelBadge'
import { formatINR, formatDateTime } from '../lib/utils'
import type { VendorDashboard } from '../types'

export default function VendorDashboard() {
  const [dashboard, setDashboard] = useState<VendorDashboard | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    vendorApi
      .getDashboard()
      .then(setDashboard)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load dashboard'))
      .finally(() => setLoading(false))
  }, [])

  const statCards = [
    {
      label: "Today's Collections",
      value: formatINR(dashboard?.today_collections || 0),
      icon: Wallet,
      colorClass: 'stat-card-green',
      iconBg: 'bg-emerald-100',
      iconColor: 'text-emerald-600',
    },
    {
      label: 'Successful Payments',
      value: dashboard?.successful_count || 0,
      icon: ShieldCheck,
      colorClass: 'stat-card-blue',
      iconBg: 'bg-primary/10',
      iconColor: 'text-primary',
    },
    {
      label: 'Pending Payments',
      value: dashboard?.pending_count || 0,
      icon: Clock,
      colorClass: 'stat-card-amber',
      iconBg: 'bg-amber-100',
      iconColor: 'text-amber-600',
    },
    {
      label: 'Suspicious Claims',
      value: dashboard?.suspicious_claims.length || 0,
      icon: TriangleAlert,
      colorClass: 'stat-card-red',
      iconBg: 'bg-red-100',
      iconColor: 'text-red-600',
      valueClass: (dashboard?.suspicious_claims.length || 0) > 0 ? 'text-red-600' : undefined,
    },
  ]

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Page Header */}
      <div className="page-header text-white">
        <div className="relative z-10 flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="h-5 w-5 text-white/80" />
              <span className="text-sm font-medium text-white/80">Vendor Protection</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Vendor Dashboard</h1>
            <p className="mt-1.5 text-sm text-white/75 font-medium">
              Verify real payments. Never trust a screenshot.
            </p>
          </div>
          <Link to="/vendor/verify">
            <Button className="bg-white text-primary hover:bg-white/90 gap-2 shadow-lg">
              <ShieldCheck className="h-4 w-4" />
              Verify Payment
            </Button>
          </Link>
        </div>
      </div>

      {error && <Alert variant="error">{error}</Alert>}

      {/* Stats */}
      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-32 w-full rounded-2xl" />)}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 stagger">
          {statCards.map((card) => (
            <div key={card.label} className={`stat-card ${card.colorClass} animate-fade-in-up`}>
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-muted-foreground font-medium">{card.label}</p>
                  <p className={`mt-2 text-2xl font-bold tracking-tight ${card.valueClass || 'text-foreground'}`}>
                    {card.value}
                  </p>
                </div>
                <div className={`rounded-xl ${card.iconBg} p-2.5`}>
                  <card.icon className={`h-5 w-5 ${card.iconColor}`} />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Main Content Grid */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Suspicious Claims */}
        <Card className="rounded-2xl border-0 shadow-md">
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <div>
              <CardTitle className="text-lg font-semibold">High Risk Payment Claims</CardTitle>
              <p className="text-xs text-muted-foreground mt-0.5">Claims requiring verification</p>
            </div>
            <TriangleAlert className="h-5 w-5 text-red-500" />
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="space-y-3">{[1, 2].map((i) => <Skeleton key={i} className="h-20 rounded-xl" />)}</div>
            ) : !dashboard?.suspicious_claims.length ? (
              <div className="py-10 text-center">
                <ShieldCheck className="h-10 w-10 text-emerald-400 mx-auto mb-3" />
                <p className="text-sm font-medium text-muted-foreground">No high risk claims today</p>
                <p className="text-xs text-muted-foreground mt-1">All payment claims are within normal range</p>
              </div>
            ) : (
              <div className="space-y-3">
                {dashboard.suspicious_claims.map((claim) => (
                  <div key={claim.transaction_id} className="rounded-xl border border-red-200 bg-gradient-to-r from-red-50 to-rose-50 p-4">
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-lg font-bold text-red-800">{formatINR(claim.amount || 0)}</p>
                      <RiskLevelBadge level={claim.risk_level || 'HIGH'} />
                    </div>
                    <p className="text-sm text-red-700">
                      <span className="font-medium">{claim.customer_name}</span>
                      {claim.claimed_at && <span className="text-red-600"> · {formatDateTime(claim.claimed_at)}</span>}
                    </p>
                    <div className="mt-3 rounded-lg bg-red-100 px-3 py-2">
                      <p className="text-xs font-bold text-red-800">⚠ Do not release order without verification</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Risk Alerts */}
        <Card className="rounded-2xl border-0 shadow-md">
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <div>
              <CardTitle className="text-lg font-semibold">Risk Alerts</CardTitle>
              <p className="text-xs text-muted-foreground mt-0.5">Real-time risk notifications</p>
            </div>
            <TrendingUp className="h-5 w-5 text-primary" />
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="space-y-3">{[1, 2].map((i) => <Skeleton key={i} className="h-16 rounded-xl" />)}</div>
            ) : !dashboard?.risk_alerts.length ? (
              <div className="py-10 text-center">
                <ShieldCheck className="h-10 w-10 text-emerald-400 mx-auto mb-3" />
                <p className="text-sm font-medium text-muted-foreground">All clear</p>
                <p className="text-xs text-muted-foreground mt-1">No risk alerts at this time</p>
              </div>
            ) : (
              <div className="space-y-3">
                {dashboard.risk_alerts.map((alert) => (
                  <div
                    key={alert.transaction_id}
                    className={`rounded-xl border p-4 ${
                      alert.severity === 'HIGH'
                        ? 'bg-red-50 border-red-200'
                        : alert.severity === 'MEDIUM'
                        ? 'bg-amber-50 border-amber-200'
                        : 'bg-gray-50 border-gray-200'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <TriangleAlert className={`h-4 w-4 mt-0.5 flex-shrink-0 ${
                        alert.severity === 'HIGH' ? 'text-red-600' :
                        alert.severity === 'MEDIUM' ? 'text-amber-600' : 'text-gray-500'
                      }`} />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-foreground">{alert.message}</p>
                        {alert.created_at && (
                          <p className="text-xs text-muted-foreground mt-1">{formatDateTime(alert.created_at)}</p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Quick Action Bar */}
      <div className="rounded-2xl bg-gradient-to-r from-primary/5 to-primary/10 border border-primary/15 p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="font-semibold text-foreground">Need to verify a payment claim?</p>
            <p className="text-sm text-muted-foreground mt-0.5">
              Never accept a screenshot as proof. Verify against trusted payment records.
            </p>
          </div>
          <Link to="/vendor/verify">
            <Button className="btn-primary-gradient gap-2">
              <ShieldCheck className="h-4 w-4" />
              Verify Now
              <ArrowRight className="h-4 w-4" />
            </Button>
          </Link>
        </div>
      </div>
    </div>
  )
}