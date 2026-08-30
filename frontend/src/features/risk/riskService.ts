import { api } from '../../services/api'
import type {
  RiskPrecheckResult,
  RiskDecision,
  ExplainRiskInput,
  ExplainRiskResult,
} from '../../types'

export interface PrecheckInput {
  amount: number
  currency?: string
  merchant_id: string
}

export const riskApi = {
  precheck: (input: PrecheckInput) =>
    api.post<RiskPrecheckResult>('/api/risk/precheck', input),

  getDecision: (transactionId: string) =>
    api.get<RiskDecision>(`/api/risk/${transactionId}`),

  explainRisk: (input: ExplainRiskInput) =>
    api.post<ExplainRiskResult>('/api/ai/explain-risk', input),
}
