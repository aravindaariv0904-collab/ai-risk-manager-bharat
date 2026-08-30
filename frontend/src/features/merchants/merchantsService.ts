import { api } from '../../services/api'
import type { Merchant } from '../../types'

export const merchantsApi = {
  list: () => api.get<Merchant[]>('/api/merchants'),

  get: (id: string) => api.get<Merchant>(`/api/merchants/${id}`),

  lookup: (params: { q?: string; phone?: string }) => {
    const searchParams = new URLSearchParams()
    if (params.q) searchParams.set('q', params.q)
    if (params.phone) searchParams.set('phone', params.phone)
    return api.get<Merchant | null>(`/api/merchants/lookup?${searchParams.toString()}`)
  },
}

