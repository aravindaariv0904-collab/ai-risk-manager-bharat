import { api } from '../../services/api'
import type { Merchant } from '../../types'

export const merchantsApi = {
  list: () => api.get<Merchant[]>('/api/merchants'),

  get: (id: string) => api.get<Merchant>(`/api/merchants/${id}`),
}
