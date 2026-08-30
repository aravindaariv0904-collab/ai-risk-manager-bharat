import { useEffect, useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import {
  Send, ShieldCheck, TriangleAlert, Wallet,
  TrendingUp, ArrowRight, Activity, Sparkles,
} from 'lucide-react'
import {
  AreaChart, Area, ResponsiveContainer, Tooltip, XAxis,
} from 'recharts'
import { paymentsApi } from '../features/payments/paymentsService'
import { Skeleton } from '../components/ui/Skeleton'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Alert } from '../components/ui/Alert'
import RiskLevelBadge from '../components/RiskLevelBadge'
import { formatINR, formatDate } from '../lib/utils'
import type { Transaction } from '../types'

export default function CitizenDashboard() {
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    paymentsApi
      .listTransactions({ limit: 50 })
      .then(({ transactions }: { transactions: Transaction[] }) => setTransactions(transactions))
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  const stats = useMemo(() => {
    const totalSpent = transactions.reduce(
      (sum, t) => sum + (t.status === 'captured' ? t.amount : 0), 0
    )
    const highRisk = transactions.filter((t) => t.risk_level === 'HIGH').length
    const mediumRisk = transactions.filter((t) => t.risk_level === 'MEDIUM').length
    const protected_ = transactions.length
    return { totalSpent, highRisk, mediumRisk, protected: protected_ }
  }, [transactions])

  // Build last 7 days chart data
  const chartData = useMemo(() => {
    const days: Record<string, number> = {}
    const today = new Date()
    for (let i = 6; i >= 0; i--) {
      const d = new Date(today)
      d.setDate(d.getDate() - i)
      days[d.toLocaleDateString('en-IN', { month: 'short', day: 'numeric' })] = 0
    }
    transactions.forEach((t) => {
      const date = new Date(t.created_at).toLocaleDateString('en-IN', { month: 'short', day: 'numeric' })
      if (days[date] !== undefined) {
        days[date] += t.amount
      }
    })
    return Object.entries(days).map(([date, amount]) => ({ date, amount }))
  }, [transactions])

  const recent = transactions.slice(0, 6)

  const statCards = [
    {
      label: 'Total Spending',
      value: formatINR(stats.totalSpent),
      icon: Wallet,
      colorClass: 'stat-card-blue',
      iconBg: 'bg-primary/10',
      iconColor: 'text-primary',
    },
    {
      label: 'Protected Transactions',
      value: stats.protected,
      icon: ShieldCheck,
      colorClass: 'stat-card-green',
      iconBg: 'bg-emerald-100',
      iconColor: 'text-emerald-600',
    },
    {
      label: 'High Risk Alerts',
      value: stats.highRisk,
      icon: TriangleAlert,
      colorClass: 'stat-card-red',
      iconBg: 'bg-red-100',
      iconColor: 'text-red-600',
      valueClass: stats.highRisk > 0 ? 'text-red-600' : undefined,
    },
    {
      label: 'Medium Risk',
      value: stats.mediumRisk,
      icon: Activity,
      colorClass: 'stat-card-amber',
      iconBg: 'bg-amber-100',
      iconColor: 'text-amber-600',
      valueClass: stats.mediumRisk > 0 ? 'text-amber-500' : undefined,
    },
  ]

  return (
    <div className="space-y-8 animate-fade-in">
      {error && <Alert variant="error">{error}</Alert>}

      {/* Page Header */}
      <div className="page-header text-white">
        <div className="relative z-10 flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="h-5 w-5 text-white/80" />
              <span className="text-sm font-medium text-white/80">AI-Powered Safety</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">
              Payment Safety Dashboard
            </h1>
            <p className="mt-1.5 text-sm text-white/75 font-medium">
              Detect · Score · Explain · Verify · Act · Learn
            </p>
          </div>
          <Link to="/pay">
            <Button className="bg-white text-primary hover:bg-white/90 gap-2 shadow-lg">
              <Send className="h-4 w-4" />
              New Payment
            </Button>
          </Link>
        </div>
      </div>

      {/* Stats Grid */}
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

      {!loading && transactions.length === 0 && (
        <div className="rounded-2xl border-2 border-dashed border-primary/20 bg-primary/5 p-12 text-center animate-fade-in">
          <ShieldCheck className="h-12 w-12 text-primary/50 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-foreground">No transactions yet</h3>
          <p className="mt-1 text-sm text-muted-foreground max-w-sm mx-auto">
            Make your first payment to see AI risk analysis in action.
          </p>
          <Link to="/pay" className="mt-4 inline-block">
            <Button>
              <Send className="h-4 w-4" />
              Make a Payment
            </Button>
          </Link>
        </div>
      )}

      {/* Chart + Recent Transactions */}
      {!loading && transactions.length > 0 && (
        <div className="grid gap-6 lg:grid-cols-5">
          {/* Spending Chart */}
          <Card className="lg:col-span-3 rounded-2xl border-0 shadow-md">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-lg font-semibold">Spending This Week</CardTitle>
                  <p className="text-xs text-muted-foreground mt-0.5">Daily transaction volume (₹)</p>
                </div>
                <TrendingUp className="h-5 w-5 text-primary" />
              </div>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={180}>
                <AreaChart data={chartData} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
                  <defs>
                    <linearGradient id="spendGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="hsl(243,75%,59%)" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="hsl(243,75%,59%)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                  <Tooltip
                    formatter={(v: number) => [formatINR(v), 'Amount']}
                    contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 24px rgba(0,0,0,0.12)', fontSize: '12px' }}
                  />
                  <Area
                    type="monotone"
                    dataKey="amount"
                    stroke="hsl(243,75%,59%)"
                    strokeWidth={2.5}
                    fill="url(#spendGrad)"
                    dot={false}
                    activeDot={{ r: 4, strokeWidth: 2 }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          {/* Recent Transactions */}
          <Card className="lg:col-span-2 rounded-2xl border-0 shadow-md">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-lg font-semibold">Recent Activity</CardTitle>
              <Link to="/history" className="text-xs text-primary hover:underline font-medium flex items-center gap-1">
                View all <ArrowRight className="h-3 w-3" />
              </Link>
            </CardHeader>
            <CardContent>
              <div className="divide-y divide-border/50">
                {recent.map((t) => (
                  <div key={t.id} className="flex items-center justify-between py-3 first:pt-0 last:pb-0 hover:bg-accent/30 -mx-2 px-2 rounded-lg transition-colors">
                    <div className="min-w-0">
                      <p className="font-medium text-sm truncate">{(t as any).merchant_name || 'Merchant'}</p>
                      <p className="text-xs text-muted-foreground mt-0.5">{formatDate(t.created_at)}</p>
                    </div>
                    <div className="flex items-center gap-2 ml-2 flex-shrink-0">
                      <RiskLevelBadge level={t.risk_level} />
                      <span className="font-semibold text-sm tabular-nums">{formatINR(t.amount)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Risk Alert Banner for HIGH risk */}
      {!loading && stats.highRisk > 0 && (
        <div className="rounded-2xl bg-red-50 border border-red-200 p-5 flex items-start gap-4 animate-fade-in">
          <div className="rounded-xl bg-red-100 p-2.5 flex-shrink-0">
            <TriangleAlert className="h-5 w-5 text-red-600" />
          </div>
          <div className="flex-1">
            <p className="font-semibold text-red-800">
              {stats.highRisk} high risk transaction{stats.highRisk > 1 ? 's' : ''} detected
            </p>
            <p className="text-sm text-red-700 mt-0.5">
              Review your transaction history for details on flagged payments.
            </p>
          </div>
          <Link to="/history">
            <Button variant="outline" className="text-red-700 border-red-200 hover:bg-red-100 text-sm">
              Review
            </Button>
          </Link>
        </div>
      )}
    </div>
  )
}