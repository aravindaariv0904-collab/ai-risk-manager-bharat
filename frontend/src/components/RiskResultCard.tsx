import React from 'react'
import {
  ShieldCheck,
  AlertTriangle,
  CheckCircle,
  Info,
  ArrowRight,
  X,
  Bot,
  RefreshCw,
  Lock,
} from 'lucide-react'
import { Button } from './ui/Button'
import { Badge } from './ui/Badge'
import { Alert } from './ui/Alert'
import { cn } from '../lib/utils'
import type { RiskPrecheckResult, RiskReason, SignalSeverity, RiskLevel, RiskAction } from '../types'

export interface RiskResultCardProps {
  result?: RiskPrecheckResult | null
  isLoading?: boolean
  error?: string | null
  onRetry?: () => void
  onCancel?: () => void
  onContinue?: () => void
  isProcessing?: boolean
  aiExplanation?: string | null
  aiRecommendation?: string | null
  isAiLoading?: boolean
  className?: string
}

// Canonical Signal Name Humanizer (Formats backend signal_name cleanly)
export function formatSignalName(rawName: string): string {
  const customMap: Record<string, string> = {
    txn_amount_spike_3x: 'Unusual transaction amount',
    txn_amount_exceeds_p95: 'Amount exceeds baseline percentile',
    txn_high_amount_new_recipient: 'High amount to new recipient',
    new_recipient_high_amount: 'High amount to new recipient',
    amount_anomaly: 'Unusual transaction amount',
    id_new_recipient: 'New recipient',
    id_unverified_recipient: 'Unverified recipient',
    new_contact_first_time: 'First-time contact',
    vel_rapid_txns_1h: 'High transaction velocity (1h)',
    vel_excessive_txns_24h: 'High daily transaction volume',
    rapid_repeated_txns: 'High transaction velocity',
    beh_unusual_hour: 'Unusual transaction hour',
    unusual_time: 'Unusual transaction hour',
    beh_failed_attempts_spike: 'Multiple failed payment attempts',
    multiple_failed_attempts: 'Multiple failed payment attempts',
    beh_unusual_category: 'Unusual merchant category',
    ml_isolation_forest_anomaly: 'ML multidimensional anomaly',
  }

  if (customMap[rawName]) {
    return customMap[rawName]
  }

  // Fallback: convert snake_case to Title Case
  return rawName
    .replace(/^(id_|txn_|beh_|vel_|ml_)/, '')
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

export function getSeverityBadge(severity: SignalSeverity) {
  switch (severity) {
    case 'HIGH':
      return <Badge variant="danger" className="text-[10px] px-2 py-0.5 font-bold uppercase">HIGH</Badge>
    case 'MEDIUM':
      return <Badge variant="warning" className="text-[10px] px-2 py-0.5 font-bold uppercase">MEDIUM</Badge>
    case 'LOW':
    default:
      return <Badge variant="outline" className="text-[10px] px-2 py-0.5 font-medium uppercase bg-slate-100 text-slate-700 border-slate-300">LOW</Badge>
  }
}

export const LEVEL_THEMES: Record<
  RiskLevel,
  {
    gradient: string
    badgeBg: string
    badgeText: string
    badgeBorder: string
    boxBg: string
    boxBorder: string
    boxText: string
    title: string
    decisionText: string
    decisionBg: string
    decisionBorder: string
    decisionTextColor: string
    defaultRecommendation: string
  }
> = {
  LOW: {
    gradient: 'from-emerald-500 to-teal-500',
    badgeBg: 'bg-emerald-100',
    badgeText: 'text-emerald-800',
    badgeBorder: 'border-emerald-300',
    boxBg: 'bg-emerald-50/70',
    boxBorder: 'border-emerald-200',
    boxText: 'text-emerald-900',
    title: 'LOW RISK',
    decisionText: 'ALLOW PAYMENT',
    decisionBg: 'bg-emerald-100/80',
    decisionBorder: 'border-emerald-300',
    decisionTextColor: 'text-emerald-900',
    defaultRecommendation: 'Safe to proceed with payment. Verified within standard baseline.',
  },
  MEDIUM: {
    gradient: 'from-amber-500 to-orange-500',
    badgeBg: 'bg-amber-100',
    badgeText: 'text-amber-800',
    badgeBorder: 'border-amber-300',
    boxBg: 'bg-amber-50/70',
    boxBorder: 'border-amber-200',
    boxText: 'text-amber-900',
    title: 'MEDIUM RISK',
    decisionText: 'STEP-UP VERIFICATION',
    decisionBg: 'bg-amber-100/80',
    decisionBorder: 'border-amber-300',
    decisionTextColor: 'text-amber-950',
    defaultRecommendation: 'Perform step-up verification (OTP/recipient confirm) before continuing.',
  },
  HIGH: {
    gradient: 'from-orange-500 to-rose-600',
    badgeBg: 'bg-orange-100',
    badgeText: 'text-orange-900',
    badgeBorder: 'border-orange-300',
    boxBg: 'bg-orange-50/80',
    boxBorder: 'border-orange-200',
    boxText: 'text-orange-950',
    title: 'HIGH RISK',
    decisionText: 'HOLD FOR REVIEW',
    decisionBg: 'bg-orange-100/90',
    decisionBorder: 'border-orange-300',
    decisionTextColor: 'text-orange-950',
    defaultRecommendation: 'Hold transaction for manual compliance and safety review.',
  },
  CRITICAL: {
    gradient: 'from-rose-600 to-red-900',
    badgeBg: 'bg-rose-100',
    badgeText: 'text-rose-900',
    badgeBorder: 'border-rose-300',
    boxBg: 'bg-rose-50/90',
    boxBorder: 'border-rose-300',
    boxText: 'text-rose-950',
    title: 'CRITICAL RISK',
    decisionText: 'BLOCK PAYMENT',
    decisionBg: 'bg-rose-200/90',
    decisionBorder: 'border-rose-400',
    decisionTextColor: 'text-rose-950',
    defaultRecommendation: 'Do not complete the payment. Review the transaction.',
  },
}

export function formatDecision(action: RiskAction | undefined, level: RiskLevel): string {
  if (action === 'BLOCK' || level === 'CRITICAL') return 'BLOCK PAYMENT'
  if (action === 'HOLD_FOR_REVIEW' || level === 'HIGH') return 'HOLD FOR REVIEW'
  if (action === 'STEP_UP_VERIFICATION' || action === 'VERIFY' || level === 'MEDIUM') return 'STEP-UP VERIFICATION'
  return 'ALLOW PAYMENT'
}

export default function RiskResultCard({
  result,
  isLoading = false,
  error = null,
  onRetry,
  onCancel,
  onContinue,
  isProcessing = false,
  aiExplanation = null,
  aiRecommendation = null,
  isAiLoading = false,
  className,
}: RiskResultCardProps) {
  // 1. Loading State
  if (isLoading) {
    return (
      <div
        className={cn('rounded-2xl border border-slate-200 bg-white p-6 shadow-md space-y-6 animate-pulse', className)}
        role="region"
        aria-label="Risk Evaluation Loading"
        aria-live="polite"
      >
        <div className="flex flex-col items-center justify-center space-y-3 pt-2">
          <div className="h-4 w-28 rounded-full bg-slate-200" />
          <div className="h-12 w-36 rounded-2xl bg-slate-200" />
          <div className="h-6 w-32 rounded-full bg-slate-200" />
        </div>

        <div className="space-y-3 rounded-xl border border-slate-100 bg-slate-50/70 p-4">
          <div className="h-4 w-40 rounded bg-slate-200" />
          <div className="h-8 w-full rounded bg-slate-200" />
        </div>

        <div className="space-y-2.5">
          <div className="h-4 w-48 rounded bg-slate-200" />
          <div className="h-12 w-full rounded-xl bg-slate-100" />
          <div className="h-12 w-full rounded-xl bg-slate-100" />
        </div>

        <div className="flex gap-3 pt-2">
          <div className="h-11 flex-1 rounded-xl bg-slate-200" />
          <div className="h-11 flex-1 rounded-xl bg-slate-200" />
        </div>
      </div>
    )
  }

  // 2. Error State
  if (error) {
    return (
      <div
        className={cn('rounded-2xl border border-red-200 bg-red-50/50 p-6 shadow-md space-y-5', className)}
        role="alert"
      >
        <div className="flex items-center gap-3 text-red-700">
          <AlertTriangle className="h-6 w-6 flex-shrink-0" />
          <div>
            <h3 className="text-base font-bold text-red-900">Risk Assessment Failed</h3>
            <p className="text-xs text-red-700 mt-0.5">{error}</p>
          </div>
        </div>

        <div className="flex gap-3 pt-2">
          {onCancel && (
            <Button variant="outline" className="flex-1 h-11 border-red-200 hover:bg-red-50 text-red-800" onClick={onCancel}>
              <X className="h-4 w-4 mr-1.5" />
              Cancel
            </Button>
          )}
          {onRetry && (
            <Button className="flex-1 h-11 bg-red-600 hover:bg-red-700 text-white font-semibold" onClick={onRetry}>
              <RefreshCw className="h-4 w-4 mr-1.5" />
              Retry Analysis
            </Button>
          )}
        </div>
      </div>
    )
  }

  // 3. Empty State (No result provided)
  if (!result) {
    return (
      <div className={cn('rounded-2xl border border-slate-200 bg-white p-8 text-center space-y-3 shadow-sm', className)}>
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 text-slate-500">
          <ShieldCheck className="h-6 w-6" />
        </div>
        <h3 className="text-base font-bold text-slate-800">No Risk Analysis Available</h3>
        <p className="text-xs text-muted-foreground max-w-xs mx-auto">
          Enter recipient details and amount above to run transaction risk intelligence.
        </p>
      </div>
    )
  }

  const level = result.risk_level || 'LOW'
  const theme = LEVEL_THEMES[level] || LEVEL_THEMES.LOW
  const decisionText = formatDecision(result.risk_action, level)
  const isBlocked = level === 'CRITICAL' || result.risk_action === 'BLOCK'
  const isHold = level === 'HIGH' || result.risk_action === 'HOLD_FOR_REVIEW'
  const recommendedAction = result.recommended_action || theme.defaultRecommendation
  const reasons = result.reasons || []

  return (
    <div
      className={cn('rounded-2xl border border-slate-200 bg-white shadow-xl overflow-hidden animate-fade-in-up', className)}
      role="region"
      aria-label="Risk Evaluation Result"
    >
      {/* Top Gradient Banner */}
      <div className={cn('h-2.5 bg-gradient-to-r', theme.gradient)} />

      <div className="p-5 sm:p-7 space-y-6">
        {/* =================================================================== */}
        {/* Section 1: RISK SCORE Header */}
        {/* =================================================================== */}
        <div className="text-center space-y-2 pt-1">
          <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground">
            RISK SCORE
          </p>
          <div className="flex items-baseline justify-center gap-1.5">
            <span
              data-testid="risk-score-value"
              className={cn(
                'text-5xl sm:text-6xl font-black tracking-tight font-mono',
                level === 'CRITICAL' ? 'text-rose-700' :
                level === 'HIGH' ? 'text-orange-600' :
                level === 'MEDIUM' ? 'text-amber-600' :
                'text-emerald-600'
              )}
            >
              {result.risk_score}
            </span>
            <span className="text-xl sm:text-2xl font-bold text-slate-400">/ 100</span>
          </div>

          <div>
            <span
              data-testid="risk-level-badge"
              className={cn(
                'inline-flex items-center gap-1.5 rounded-full px-4 py-1 text-xs sm:text-sm font-extrabold uppercase tracking-wide border shadow-sm',
                theme.badgeBg,
                theme.badgeText,
                theme.badgeBorder
              )}
            >
              {level === 'CRITICAL' && <AlertTriangle className="h-4 w-4 text-rose-700" />}
              {level === 'HIGH' && <AlertTriangle className="h-4 w-4 text-orange-600" />}
              {level === 'MEDIUM' && <Info className="h-4 w-4 text-amber-600" />}
              {level === 'LOW' && <CheckCircle className="h-4 w-4 text-emerald-600" />}
              {theme.title}
            </span>
          </div>
        </div>

        {/* =================================================================== */}
        {/* Section 2: DECISION & RECOMMENDED ACTION */}
        {/* =================================================================== */}
        <div className={cn('rounded-xl border p-4 sm:p-5 space-y-3.5', theme.boxBg, theme.boxBorder)}>
          {/* Decision */}
          <div>
            <p className="text-[11px] font-extrabold uppercase tracking-wider text-slate-600">
              DECISION
            </p>
            <div className="mt-1 flex items-center gap-2">
              <span
                data-testid="risk-decision-banner"
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-lg px-3 py-1 text-sm font-black uppercase tracking-wide border',
                  theme.decisionBg,
                  theme.decisionBorder,
                  theme.decisionTextColor
                )}
              >
                {isBlocked && <Lock className="h-3.5 w-3.5" />}
                {decisionText}
              </span>
            </div>
          </div>

          {/* Recommended Action */}
          <div className="pt-2 border-t border-slate-200/60">
            <p className="text-[11px] font-extrabold uppercase tracking-wider text-slate-600">
              RECOMMENDED ACTION
            </p>
            <p
              data-testid="recommended-action-text"
              className={cn('mt-1 text-xs sm:text-sm font-semibold leading-relaxed', theme.boxText)}
            >
              {recommendedAction}
            </p>
            {result.human_explanation && result.human_explanation !== recommendedAction && (
              <p className="mt-1 text-xs text-slate-600 leading-normal">
                {result.human_explanation}
              </p>
            )}
          </div>
        </div>

        {/* =================================================================== */}
        {/* Section 3: WHY THIS PAYMENT WAS FLAGGED (Structured Breakdown) */}
        {/* =================================================================== */}
        <div className="space-y-3" data-testid="signals-section">
          <div className="flex items-center justify-between">
            <h4 className="text-xs sm:text-sm font-extrabold uppercase tracking-wide text-foreground flex items-center gap-1.5">
              <span>WHY THIS PAYMENT WAS FLAGGED</span>
            </h4>
            <span className="text-[11px] font-semibold text-muted-foreground">
              {reasons.length} {reasons.length === 1 ? 'signal' : 'signals'}
            </span>
          </div>

          {reasons.length > 0 ? (
            <div className="rounded-xl border border-slate-200 bg-slate-50/50 overflow-hidden divide-y divide-slate-200/80">
              {reasons.map((r: RiskReason, idx: number) => {
                const displayName = formatSignalName(r.signal_name)
                return (
                  <div
                    key={`${r.signal_name}-${idx}`}
                    data-testid={`signal-row-${idx}`}
                    className="p-3.5 sm:p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 transition-colors hover:bg-white"
                  >
                    <div className="space-y-1 flex-1 pr-2">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-bold text-xs sm:text-sm text-foreground">
                          {displayName}
                        </span>
                        {getSeverityBadge(r.severity)}
                      </div>
                      <p className="text-xs text-slate-600 leading-relaxed">
                        {r.reason}
                      </p>
                    </div>

                    <div className="flex items-center justify-end sm:justify-center flex-shrink-0 self-start sm:self-center">
                      <span className="inline-flex items-center rounded-md bg-slate-200/80 px-2 py-0.5 font-mono text-xs font-bold text-slate-800">
                        +{r.score_impact}
                      </span>
                    </div>
                  </div>
                )
              })}

              {/* Total Score Footer Row */}
              <div className="p-3.5 sm:p-4 bg-slate-100/80 flex items-center justify-between font-bold text-xs sm:text-sm">
                <span className="uppercase text-slate-700 tracking-wide font-extrabold">Total Risk Score</span>
                <span className="font-mono text-sm sm:text-base text-foreground font-black">
                  {result.risk_score}
                </span>
              </div>
            </div>
          ) : (
            <div
              data-testid="empty-signals-state"
              className="rounded-xl border border-emerald-200 bg-emerald-50/60 p-4 flex items-center gap-3 text-xs sm:text-sm text-emerald-900"
            >
              <CheckCircle className="h-5 w-5 text-emerald-600 flex-shrink-0" />
              <div>
                <p className="font-bold">No risk signals detected</p>
                <p className="text-xs text-emerald-700 mt-0.5">
                  All transaction metrics are within normal baseline behavior.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* =================================================================== */}
        {/* Section 4: AI Explanation (If Available) */}
        {/* =================================================================== */}
        {isAiLoading ? (
          <div className="rounded-xl bg-primary/5 border border-primary/10 p-4 space-y-2 animate-pulse">
            <div className="flex items-center gap-2">
              <Bot className="h-4 w-4 text-primary animate-spin" />
              <span className="text-xs font-bold text-primary">Generating AI Intelligence...</span>
            </div>
            <div className="h-3 w-4/5 rounded bg-primary/10" />
            <div className="h-3 w-3/5 rounded bg-primary/10" />
          </div>
        ) : aiExplanation ? (
          <div className="rounded-xl bg-gradient-to-br from-primary/5 to-primary/10 border border-primary/15 p-4 space-y-2">
            <div className="flex items-center gap-2">
              <Bot className="h-4 w-4 text-primary" />
              <span className="text-xs font-bold text-primary uppercase tracking-wide">AI Explanation</span>
            </div>
            <p className="text-xs sm:text-sm text-foreground leading-relaxed">{aiExplanation}</p>
            {aiRecommendation && (
              <div className="mt-2 pt-2 border-t border-primary/10 flex items-center gap-2 text-xs font-semibold text-primary">
                <ArrowRight className="h-3.5 w-3.5 flex-shrink-0" />
                <span>{aiRecommendation}</span>
              </div>
            )}
          </div>
        ) : null}

        {/* =================================================================== */}
        {/* Section 5: Action Buttons */}
        {/* =================================================================== */}
        <div className="pt-2 flex flex-col sm:flex-row gap-3">
          {onCancel && (
            <Button
              type="button"
              variant="outline"
              className="h-11 sm:flex-1 text-sm font-semibold border-slate-300 hover:bg-slate-50"
              onClick={onCancel}
              disabled={isProcessing}
            >
              <X className="h-4 w-4 mr-1.5" />
              Cancel
            </Button>
          )}

          {isBlocked ? (
            <Button
              type="button"
              disabled
              data-testid="blocked-action-button"
              className="h-11 sm:flex-1 text-sm font-bold bg-rose-100 text-rose-800 border border-rose-300 cursor-not-allowed opacity-90"
            >
              <Lock className="h-4 w-4 mr-1.5 text-rose-700" />
              Transaction Blocked
            </Button>
          ) : (
            <Button
              type="button"
              data-testid="continue-action-button"
              className={cn(
                'h-11 sm:flex-1 text-sm font-bold shadow-md transition-all',
                isHold
                  ? 'bg-orange-600 hover:bg-orange-700 text-white'
                  : level === 'MEDIUM'
                  ? 'bg-amber-500 hover:bg-amber-600 text-white'
                  : 'btn-primary-gradient'
              )}
              onClick={onContinue}
              loading={isProcessing}
            >
              <ArrowRight className="h-4 w-4 mr-1.5" />
              {isHold
                ? 'Submit for Manual Review'
                : level === 'MEDIUM'
                ? 'Verify Recipient & Proceed'
                : 'Continue Payment'}
            </Button>
          )}
        </div>

        {/* Footer Security Notice */}
        <p className="text-[11px] text-center text-muted-foreground">
          Protected by Bharat AI Risk Engine · Powered by canonical ML anomaly models
        </p>
      </div>
    </div>
  )
}
