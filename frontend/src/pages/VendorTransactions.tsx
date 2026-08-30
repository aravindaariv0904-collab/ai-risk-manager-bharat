import { useEffect, useState, useCallback } from 'react'
import { vendorApi } from '../features/vendor/vendorService'
import RiskLevelBadge from '../components/RiskLevelBadge'
import { Badge } from '../components/ui/Badge'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card'
import { Select } from '../components/ui/Select'
import { Alert } from '../components/ui/Alert'
import { formatINR, formatDate } from '../lib/utils'

export default function VendorTransactions() {
  const [transactions, setTransactions] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(0)
  const LIMIT = 20

  const fetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await vendorApi.listPayments({
        limit: LIMIT,
        offset: page * LIMIT,
        status: (statusFilter || undefined) as import('../types').TransactionStatus | undefined,
      })
      setTransactions(res.transactions)
      setTotal(res.total)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load payments')
    } finally {
      setLoading(false)
    }
  }, [page, statusFilter])

  useEffect(() => { fetch() }, [fetch])

  const totalPages = Math.ceil(total / LIMIT)

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Vendor Transactions</h1>
          <p className="text-sm text-muted-foreground">All payments you received with risk analysis.</p>
        </div>
        <div className="w-48">
          <Select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(0) }}>
            <option value="">All statuses</option>
            <option value="captured">Captured</option>
            <option value="pending">Pending</option>
            <option value="failed">Failed</option>
          </Select>
        </div>
      </div>

      {error && <Alert variant="error">{error}</Alert>}

      <Card>
        <CardHeader>
          <CardTitle>{total} received payments</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => <div key={i} className="h-14 animate-pulse rounded-md bg-gray-100" />)}
            </div>
          ) : transactions.length === 0 ? (
            <p className="py-10 text-center text-sm text-muted-foreground">
              No payments received yet.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs text-muted-foreground">
                    <th className="pb-2">Date</th>
                    <th className="pb-2">Payment ID</th>
                    <th className="pb-2 text-right">Amount</th>
                    <th className="pb-2 text-center">Status</th>
                    <th className="pb-2 text-center">Risk</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {transactions.map((t) => (
                    <tr key={t.id}>
                      <td className="py-3">{formatDate(t.created_at)}</td>
                      <td className="py-3 font-mono text-xs">{t.razorpay_payment_id || '—'}</td>
                      <td className="py-3 text-right font-semibold">{formatINR(t.amount)}</td>
                      <td className="py-3 text-center">
                        <Badge variant={t.status === 'captured' ? 'success' : t.status === 'failed' ? 'danger' : 'outline'}>
                          {t.status}
                        </Badge>
                      </td>
                      <td className="py-3 text-center">
                        <RiskLevelBadge level={t.risk_level} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {totalPages > 1 && (
            <div className="mt-6 flex items-center justify-between">
              <button
                className="text-sm text-primary disabled:opacity-50"
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </button>
              <span className="text-sm text-muted-foreground">
                Page {page + 1} of {totalPages}
              </span>
              <button
                className="text-sm text-primary disabled:opacity-50"
                disabled={page >= totalPages - 1}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}