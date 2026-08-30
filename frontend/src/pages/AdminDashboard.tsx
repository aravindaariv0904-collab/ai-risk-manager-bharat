import { useEffect, useState } from 'react'
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend,
  LineChart, Line, AreaChart, Area,
} from 'recharts'
import {
  TrendingUp, ShieldAlert, AlertTriangle, CheckCircle, Activity, Layers, Sparkles,
} from 'lucide-react'
import { adminApi } from '../features/admin/adminService'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card'
import { Alert } from '../components/ui/Alert'
import { Skeleton } from '../components/ui/Skeleton'
import type { AdminDashboard, ChartDataPoint } from '../types'
import { formatINR } from '../lib/utils'

const RISK_COLORS = {
  LOW: '#10b981',
  MEDIUM: '#f59e0b',
  HIGH: '#ef4444',
}

const CHART_THEME = {
  grid: '#f1f5f9',
  axis: '#94a3b8',
}

export default function AdminDashboard() {
  const [dashboard, setDashboard] = useState<AdminDashboard | null>(null)
  const [riskDist, setRiskDist] = useState<ChartDataPoint[]>([])
  const [volume, setVolume] = useState<ChartDataPoint[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      adminApi.getDashboard(),
      adminApi.getRiskDistribution(),
      adminApi.getTransactionVolume(30),
    ])
      .then(([d, r, v]) => {
        setDashboard(d)
        setRiskDist(r.data)
        setVolume(v.data)
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load admin data'))
      .finally(() => setLoading(false))
  }, [])

  const statCards = [
    { label: 'Total Transactions', value: dashboard?.total_transactions ?? 0, icon: Layers, color: 'text-foreground', bg: 'bg-gray-100' },
    { label: 'Low Risk', value: dashboard?.low_risk ?? 0, icon: CheckCircle, color: 'text-emerald-600', bg: 'bg-emerald-100', topColor: 'stat-card-green' },
    { label: 'Medium Risk', value: dashboard?.medium_risk ?? 0, icon: AlertTriangle, color: 'text-amber-600', bg: 'bg-amber-100', topColor: 'stat-card-amber' },
    { label: 'High Risk', value: dashboard?.high_risk ?? 0, icon: ShieldAlert, color: 'text-red-600', bg: 'bg-red-100', topColor: 'stat-card-red' },
    { label: 'Verified Payments', value: dashboard?.verified_payments ?? 0, icon: CheckCircle, color: 'text-primary', bg: 'bg-primary/10', topColor: 'stat-card-blue' },
    { label: 'Suspicious', value: dashboard?.suspicious_count ?? 0, icon: Activity, color: 'text-rose-600', bg: 'bg-rose-100', topColor: 'stat-card-red' },
  ]

  if (error) return <Alert variant="error">{error}</Alert>

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Admin Header */}
      <div className="page-header text-white">
        <div className="relative z-10">
          <div className="flex items-center gap-2 mb-2">
            <Sparkles className="h-5 w-5 text-white/80" />
            <span className="text-sm font-medium text-white/80">Admin Center</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Risk Analytics Overview</h1>
          <p className="mt-1.5 text-sm text-white/75 font-medium">
            Real-time transaction risk scoring and anomaly detection telemetry
          </p>
        </div>
      </div>

      {/* Stats Grid */}
      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1,2,3,4,5,6].map((i) => <Skeleton key={i} className="h-28 rounded-2xl" />)}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 stagger">
          {statCards.map((card) => (
            <div key={card.label} className={`stat-card ${card.topColor || ''} animate-fade-in-up`}>
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-muted-foreground font-medium">{card.label}</p>
                  <p className={`mt-2 text-2xl font-bold tracking-tight ${card.color}`}>
                    {card.value.toLocaleString('en-IN')}
                  </p>
                </div>
                <div className={`rounded-xl ${card.bg} p-2.5`}>
                  <card.icon className={`h-5 w-5 ${card.color}`} />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Charts Row 1 */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Risk Distribution Pie */}
        <Card className="rounded-2xl border-0 shadow-md">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg font-semibold">Risk Distribution</CardTitle>
              <Activity className="h-5 w-5 text-muted-foreground" />
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <Skeleton className="h-64 rounded-xl" />
            ) : riskDist.length === 0 ? (
              <div className="flex h-64 items-center justify-center">
                <p className="text-sm text-muted-foreground">No transaction data yet</p>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie
                    data={riskDist}
                    dataKey="value"
                    nameKey="label"
                    cx="50%"
                    cy="50%"
                    outerRadius={100}
                    innerRadius={55}
                    paddingAngle={3}
                    label={({ label, percent }) => `${label} ${(percent * 100).toFixed(0)}%`}
                    labelLine={false}
                  >
                    {riskDist.map((entry) => (
                      <Cell
                        key={entry.label}
                        fill={RISK_COLORS[entry.label as keyof typeof RISK_COLORS] || '#94a3b8'}
                        strokeWidth={0}
                      />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(v: number) => [v, 'Transactions']}
                    contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 24px rgba(0,0,0,0.1)', fontSize: '12px' }}
                  />
                  <Legend
                    formatter={(value) => <span style={{ fontSize: '12px', color: '#64748b' }}>{value}</span>}
                  />
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* Transaction Volume Area Chart */}
        <Card className="rounded-2xl border-0 shadow-md">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg font-semibold">Transactions by Day</CardTitle>
              <TrendingUp className="h-5 w-5 text-primary" />
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <Skeleton className="h-64 rounded-xl" />
            ) : volume.length === 0 ? (
              <div className="flex h-64 items-center justify-center">
                <p className="text-sm text-muted-foreground">No data yet</p>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={280}>
                <AreaChart data={volume} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
                  <defs>
                    <linearGradient id="volGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="hsl(243,75%,59%)" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="hsl(243,75%,59%)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_THEME.grid} />
                  <XAxis dataKey="label" tick={{ fontSize: 10, fill: CHART_THEME.axis }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 10, fill: CHART_THEME.axis }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 24px rgba(0,0,0,0.1)', fontSize: '12px' }} />
                  <Area type="monotone" dataKey="value" name="Transactions" stroke="hsl(243,75%,59%)" strokeWidth={2.5} fill="url(#volGrad)" dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Bar Chart - Full width */}
      <Card className="rounded-2xl border-0 shadow-md">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-lg font-semibold">Transaction Volume (Last 30 Days)</CardTitle>
              <p className="text-xs text-muted-foreground mt-0.5">Daily transaction count</p>
            </div>
            <Layers className="h-5 w-5 text-muted-foreground" />
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <Skeleton className="h-72 rounded-xl" />
          ) : volume.length === 0 ? (
            <div className="flex h-72 items-center justify-center">
              <p className="text-sm text-muted-foreground">No data available</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={volume} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_THEME.grid} />
                <XAxis dataKey="label" tick={{ fontSize: 10, fill: CHART_THEME.axis }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 10, fill: CHART_THEME.axis }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 24px rgba(0,0,0,0.1)', fontSize: '12px' }} />
                <Bar dataKey="value" name="Transactions" fill="hsl(243,75%,59%)" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>
    </div>
  )
}