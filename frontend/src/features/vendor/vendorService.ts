import { api } from '../../services/api'
import type {
  VendorDashboard,
  PaymentVerificationResult,
  Transaction,
  TransactionStatus,
} from '../../types'

export interface VendorPaymentsResponse {
  transactions: Transaction[]
  total: number
}

export interface VerifyByDetailsInput {
  payment_id?: string
  amount?: number
  customer_phone?: string
}

export const vendorApi = {
  getDashboard: () => api.get<VendorDashboard>('/api/vendor/dashboard'),

  listPayments: (
    filters?: { status?: TransactionStatus; limit?: number; offset?: number },
  ) => {
    const params = new URLSearchParams()
    if (filters?.status) params.set('status', filters.status)
    if (filters?.limit) params.set('limit', String(filters.limit))
    if (filters?.offset) params.set('offset', String(filters.offset))
    const qs = params.toString()
    return api.get<VendorPaymentsResponse>(
      `/api/vendor/payments${qs ? `?${qs}` : ''}`,
    )
  },

  verifyById: (paymentId: string) =>
    api.get<PaymentVerificationResult>(
      `/api/vendor/payment-verification/${paymentId}`,
    ),

  verifyByDetails: (input: VerifyByDetailsInput) =>
    api.post<PaymentVerificationResult>(
      '/api/vendor/payment-verification',
      input,
    ),
}
