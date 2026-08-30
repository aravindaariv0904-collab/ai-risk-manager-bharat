import { api } from '../../services/api'
import type { AssistantResult } from '../../types'

export interface AssistantQueryInput {
  query: string
  context?: Record<string, unknown>
}

export const aiApi = {
  query: (input: AssistantQueryInput) =>
    api.post<AssistantResult>('/api/ai/assistant', input),

  transactionSummary: (transactionId: string) =>
    api.get<{ summary: string }>(`/api/ai/transaction-summary/${transactionId}`),
}
