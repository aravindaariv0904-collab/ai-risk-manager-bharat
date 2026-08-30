import { api } from '../../services/api'
import type {
  Transaction,
  CreateOrderResult,
  TransactionStatus,
} from '../../types'

export interface CreateOrderInput {
  amount: number
  currency?: string
  merchant_id: string
}

export interface TransactionFilter {
  status?: TransactionStatus
  limit?: number
  offset?: number
}

export interface TransactionListResponse {
  transactions: Transaction[]
  total: number
}

export const paymentsApi = {
  createOrder: (input: CreateOrderInput) =>
    api.post<CreateOrderResult>('/api/payments/create-order', input),

  getPaymentStatus: (paymentId: string) =>
    api.get<{ payment_id: string; status: string; amount: number }>(
      `/api/payments/${paymentId}/status`,
    ),

  listTransactions: (filters?: TransactionFilter) => {
    const params = new URLSearchParams()
    if (filters?.status) params.set('status', filters.status)
    if (filters?.limit) params.set('limit', String(filters.limit))
    if (filters?.offset) params.set('offset', String(filters.offset))
    const qs = params.toString()
    return api.get<TransactionListResponse>(
      `/api/transactions${qs ? `?${qs}` : ''}`,
    )
  },

  getTransaction: (id: string) =>
    api.get<Transaction>(`/api/transactions/${id}`),
}
