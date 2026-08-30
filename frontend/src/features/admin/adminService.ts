import { api } from '../../services/api'
import type { AdminDashboard, ChartDataPoint } from '../../types'

export const adminApi = {
  getDashboard: () => api.get<AdminDashboard>('/api/admin/dashboard'),

  getRiskDistribution: () =>
    api.get<{ data: ChartDataPoint[] }>('/api/admin/risk-distribution'),

  getTransactionVolume: (days = 30) =>
    api.get<{ data: ChartDataPoint[] }>(
      `/api/admin/transaction-volume?days=${days}`,
    ),
}
