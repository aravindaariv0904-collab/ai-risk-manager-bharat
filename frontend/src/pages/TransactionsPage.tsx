import { useEffect, useState, useCallback } from 'react'
import { paymentsApi } from '../features/payments/paymentsService'
import RiskLevelBadge from '../components/RiskLevelBadge'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Select } from '../components/ui/Select'
import { Alert } from '../components/ui/Alert'
import { ProtectedTransactionRow } from '../components/ProtectedTransactionRow'
import { formatINR, formatDate } from '../lib/utils'
import type { Transaction } from '../types'

export default function TransactionsPage() {
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [total, setTotal] = useState(0)
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(0)
  const LIMIT = 20

  const fetchTransactions = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await paymentsApi.listTransactions({
        limit: LIMIT,
        offset: page * LIMIT,
        status: (statusFilter || undefined) as import('../types').TransactionStatus | undefined,
      })
      setTransactions(res.transactions)
      setTotal(res.total)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load transactions')
    } finally {
      setLoading(false)
    }
  }, [page, statusFilter])

  useEffect(() => {
    fetchTransactions()
  }, [fetchTransactions])

  const totalPages = Math.ceil(total / LIMIT)

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Transaction History</h1>
          <p className="text-sm text-muted-foreground">Every payment protected by AI risk analysis.</p>
        </div>
        <div className="w-48">
          <Select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(0) }}>
            <option value="">All statuses</option>
            <option value="captured">Captured</option>
            <option value="pending">Pending</option>
            <option value="failed">Failed</option>
            <option value="created">Created</option>
          </Select>
        </div>
      </div>

      {error && <Alert variant="error">{error}</Alert>}

      <Card>
        <CardHeader>
          <CardTitle>{total} transactions</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => <div key={i} className="h-14 animate-pulse rounded-md bg-gray-100" />)}
            </div>
          ) : transactions.length === 0 ? (
            <p className="py-10 text-center text-sm text-muted-foreground">
              No transactions found. Adjust the filters or make a new payment.
            </p>
          ) : (
            <div className="divide-y">
              {transactions.map((t) => (
                <div key={t.id} className="flex items-center justify-between gap-4 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium">{t.merchant_name || 'Merchant'}</p>
                    <p className="text-xs text-muted-foreground">{formatDate(t.created_at)}</p>
                  </div>
                  <div className="hidden md:flex items-center gap-2">
                    <ProtectedTransactionRow txn={t} />
                    <Badge variant={t.status === 'captured' ? 'success' : t.status === 'failed' ? 'danger' : 'outline'}>
                      {t.status}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-3">
                    <RiskLevelBadge level={t.risk_level} />
                    <span className="font-semibold">{formatINR(t.amount)}</span>
                  </div>
                </div>
              ))}
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