export type UserRole = 'citizen' | 'merchant' | 'admin'
export type Language = 'en' | 'hi' | 'ta'
export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
export type RiskAction = 'ALLOW' | 'STEP_UP_VERIFICATION' | 'HOLD_FOR_REVIEW' | 'BLOCK' | 'VERIFY' | 'WARN'
export type TransactionStatus = 'created' | 'pending' | 'captured' | 'failed' | 'refunded'
export type SignalSeverity = 'LOW' | 'MEDIUM' | 'HIGH'

export interface CategoryScores {
  identity_trust: number
  transaction_anomaly: number
  behavioral_anomaly: number
  velocity_network: number
  ml_anomaly: number
}

export interface Profile {
  id: string
  auth_user_id: string
  name: string
  phone: string | null
  role: UserRole
  language: Language
  created_at: string
}

export interface Merchant {
  id: string
  user_id: string
  business_name: string
  business_category: string | null
  phone?: string | null
  upi_id?: string | null
  is_verified?: boolean
  risk_profile: Record<string, unknown>
  created_at: string
}

export interface Transaction {
  id: string
  razorpay_payment_id: string | null
  razorpay_order_id: string | null
  payer_id: string
  merchant_id: string
  amount: number
  currency: string
  status: TransactionStatus
  risk_score: number | null
  risk_level: RiskLevel | null
  risk_action: RiskAction | null
  created_at: string
  updated_at: string
  merchant_name?: string
}

export interface RiskReason {
  signal_name: string
  category?: string | null
  reason: string
  severity: SignalSeverity
  score_impact: number
}

export interface RiskPrecheckResult {
  transaction_id: string
  risk_score: number
  risk_level: RiskLevel
  risk_action: RiskAction
  reasons: RiskReason[]
  recommended_action: string
  human_explanation?: string | null
  explanation?: string | null
  model_version?: string
  category_scores?: CategoryScores
  explanation_data?: Record<string, unknown>
}

export interface RiskDecision {
  transaction_id: string
  score: number
  level: RiskLevel
  action: RiskAction
  explanation: string | null
  model_version: string
  reasons: RiskReason[]
  category_scores?: CategoryScores
  explanation_data?: Record<string, unknown>
  created_at?: string
}

export interface ExplainRiskInput {
  risk_score: number
  risk_level: RiskLevel
  reasons: RiskReason[]
  language: Language
}

export interface ExplainRiskResult {
  explanation: string
  recommendation: string
}

export interface CreateOrderResult {
  order_id: string
  amount: number
  currency: string
  key_id: string
}

export interface VendorDashboard {
  today_collections: number
  successful_count: number
  pending_count: number
  suspicious_claims: SuspiciousClaim[]
  risk_alerts: RiskAlert[]
}

export interface SuspiciousClaim {
  transaction_id: string
  amount: number
  customer_name: string
  claimed_at: string
  risk_level: RiskLevel
}

export interface RiskAlert {
  transaction_id: string
  type: string
  message: string
  severity: SignalSeverity
  created_at: string
}

export interface PaymentVerificationResult {
  verified: boolean
  payment_id: string | null
  amount: number | null
  status: string | null
  captured_at: string | null
  risk_level: RiskLevel | null
  message: string
}

export interface AdminDashboard {
  total_transactions: number
  low_risk: number
  medium_risk: number
  high_risk: number
  suspicious_count: number
  verified_payments: number
  unverified_claims: number
}

export interface ChartDataPoint {
  label: string
  value: number
}

export interface AssistantResult {
  answer: string
  data_sources: string[]
}

export interface PaymentClaims {
  claims: PaymentClaim[]
}

export interface PaymentClaim {
  id: string
  merchant_id: string
  amount: number
  status: 'verified' | 'unverified' | 'pending'
  claimed_at: string
  customer_name: string
}