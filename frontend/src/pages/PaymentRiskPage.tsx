import { useState, useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { ShieldCheck, ArrowRight, X, Bot, AlertTriangle, CheckCircle, Info } from 'lucide-react'
import { merchantsApi } from '../features/merchants/merchantsService'
import { riskApi } from '../features/risk/riskService'
import { paymentsApi } from '../features/payments/paymentsService'
import RiskScoreGauge from '../components/RiskScoreGauge'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Label } from '../components/ui/Label'
import { Select } from '../components/ui/Select'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card'
import { Alert } from '../components/ui/Alert'
import { formatINR } from '../lib/utils'
import type { Merchant, RiskPrecheckResult } from '../types'
import { cn } from '../lib/utils'

const schema = z.object({
  amount: z.coerce
    .number({ invalid_type_error: 'Enter a valid amount' })
    .int('Amount must be in whole rupees')
    .positive('Amount must be greater than 0')
    .max(1000000, 'Maximum transaction limit is ₹10,00,000'),
  merchant_id: z.string().min(1, 'Select a merchant'),
})

type FormValues = z.infer<typeof schema>

const RISK_CONFIG = {
  LOW: {
    gradient: 'from-emerald-500 to-teal-500',
    bg: 'bg-emerald-50',
    border: 'border-emerald-200',
    text: 'text-emerald-800',
    badge: 'bg-emerald-100 text-emerald-700',
    icon: CheckCircle,
    label: 'LOW RISK',
    message: 'This payment looks safe to proceed.',
    buttonVariant: 'success' as const,
    buttonLabel: 'Continue Payment',
  },
  MEDIUM: {
    gradient: 'from-amber-500 to-orange-500',
    bg: 'bg-amber-50',
    border: 'border-amber-200',
    text: 'text-amber-800',
    badge: 'bg-amber-100 text-amber-700',
    icon: Info,
    label: 'MEDIUM RISK',
    message: 'Please verify the recipient before proceeding.',
    buttonVariant: 'warning' as const,
    buttonLabel: 'I Verified — Continue',
  },
  HIGH: {
    gradient: 'from-red-500 to-rose-600',
    bg: 'bg-red-50',
    border: 'border-red-200',
    text: 'text-red-800',
    badge: 'bg-red-100 text-red-700',
    icon: AlertTriangle,
    label: 'HIGH RISK',
    message: 'Strong warning: Verify the recipient carefully before proceeding.',
    buttonVariant: 'destructive' as const,
    buttonLabel: 'Proceed Anyway (High Risk)',
  },
}

export default function PaymentRiskPage() {
  const [merchants, setMerchants] = useState<Merchant[]>([])
  const [loadingMerchants, setLoadingMerchants] = useState(true)
  const [result, setResult] = useState<RiskPrecheckResult | null>(null)
  const [selectedMerchant, setSelectedMerchant] = useState<Merchant | null>(null)
  const [explanation, setExplanation] = useState<string | null>(null)
  const [recommendation, setRecommendation] = useState<string | null>(null)
  const [checking, setChecking] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [aiLoading, setAiLoading] = useState(false)
  const [completed, setCompleted] = useState(false)
  const [orderId, setOrderId] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { amount: 250, merchant_id: '' },
  })

  const amount = watch('amount')
  const merchantId = watch('merchant_id')

  useEffect(() => {
    merchantsApi
      .list()
      .then(setMerchants)
      .catch((err) => setError(err.message))
      .finally(() => setLoadingMerchants(false))
  }, [])

  useEffect(() => {
    if (merchantId && merchants.length) {
      setSelectedMerchant(merchants.find((m) => m.id === merchantId) || null)
    }
  }, [merchantId, merchants])

  async function onPrecheck(values: FormValues) {
    setError(null)
    setChecking(true)
    setResult(null)
    setExplanation(null)
    setRecommendation(null)

    try {
      const res = await riskApi.precheck({
        amount: values.amount * 100, // Convert rupees to paise
        merchant_id: values.merchant_id,
      })
      setResult(res)

      // Fetch AI explanation in parallel
      setAiLoading(true)
      try {
        const ai = await riskApi.explainRisk({
          risk_score: res.risk_score,
          risk_level: res.risk_level,
          reasons: res.reasons,
          language: 'en',
        })
        setExplanation(ai.explanation)
        setRecommendation(ai.recommendation)
      } catch {
        setExplanation(null)
      } finally {
        setAiLoading(false)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Risk check failed. Please try again.')
    } finally {
      setChecking(false)
    }
  }

  async function onContinue() {
    if (!result) return
    setProcessing(true)
    setError(null)
    try {
      const order = await paymentsApi.createOrder({
        amount: amount * 100,
        merchant_id: result.transaction_id, // use merchant from the precheck context
      })
      setOrderId(order.order_id)
      setCompleted(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Payment initiation failed')
    } finally {
      setProcessing(false)
    }
  }

  function onCancel() {
    setResult(null)
    setExplanation(null)
    setRecommendation(null)
  }

  const riskConfig = result ? RISK_CONFIG[result.risk_level as keyof typeof RISK_CONFIG] || RISK_CONFIG.MEDIUM : null

  if (completed) {
    return (
      <div className="mx-auto max-w-lg space-y-6 animate-fade-in-up">
        <div className="rounded-2xl bg-gradient-to-br from-emerald-50 to-teal-50 border border-emerald-200 p-8 text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-100">
            <CheckCircle className="h-8 w-8 text-emerald-600" />
          </div>
          <h2 className="text-xl font-bold text-emerald-900">Payment Order Created</h2>
          <p className="mt-2 text-sm text-emerald-700">
            Razorpay order <span className="font-mono font-bold">{orderId}</span> has been created.
          </p>
          <p className="mt-2 text-xs text-emerald-600">
            In production, the payment gateway would now open. A webhook will confirm the final payment status.
          </p>
          <div className="mt-6 flex gap-3 justify-center">
            <Button
              variant="outline"
              onClick={() => { setCompleted(false); setResult(null); setExplanation(null); setOrderId(null); }}
            >
              Make Another Payment
            </Button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-lg space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Payment Risk Check</h1>
        <p className="text-sm text-muted-foreground mt-1">
          AI analyses every payment before you pay — powered by real transaction intelligence.
        </p>
      </div>

      {error && <Alert variant="error">{error}</Alert>}

      {/* Step 1: Payment Form */}
      {!result && (
        <Card className="rounded-2xl border-0 shadow-md animate-fade-in-up">
          <CardHeader className="pb-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
                <ShieldCheck className="h-5 w-5 text-primary" />
              </div>
              <div>
                <CardTitle>Payment Details</CardTitle>
                <CardDescription>Risk is checked before you pay — always.</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit(onPrecheck)} className="space-y-5">
              <div className="space-y-2">
                <Label htmlFor="amount" className="font-semibold text-sm">Amount (₹)</Label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground font-semibold">₹</span>
                  <Input
                    id="amount"
                    type="number"
                    inputMode="numeric"
                    min={1}
                    placeholder="250"
                    className="pl-8 text-lg font-semibold"
                    {...register('amount')}
                  />
                </div>
                {errors.amount && <p className="text-sm text-red-600">{errors.amount.message}</p>}
              </div>

              <div className="space-y-2">
                <Label htmlFor="merchant_id" className="font-semibold text-sm">Merchant / Vendor</Label>
                <Select
                  id="merchant_id"
                  disabled={loadingMerchants}
                  className="h-11"
                  {...register('merchant_id')}
                >
                  <option value="">{loadingMerchants ? 'Loading merchants...' : 'Select a merchant'}</option>
                  {merchants.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.business_name}{m.business_category ? ` — ${m.business_category}` : ''}
                    </option>
                  ))}
                </Select>
                {errors.merchant_id && <p className="text-sm text-red-600">{errors.merchant_id.message}</p>}
              </div>

              {selectedMerchant && amount > 0 && (
                <div className="rounded-xl bg-primary/5 border border-primary/10 p-4 flex items-center justify-between">
                  <div>
                    <p className="text-xs text-muted-foreground">Paying to</p>
                    <p className="font-semibold text-sm">{selectedMerchant.business_name}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-muted-foreground">Amount</p>
                    <p className="text-xl font-bold text-primary">{formatINR(amount * 100)}</p>
                  </div>
                </div>
              )}

              <Button
                type="submit"
                className="w-full h-12 text-base font-semibold btn-primary-gradient"
                loading={checking}
                disabled={loadingMerchants}
              >
                <ShieldCheck className="h-5 w-5" />
                Analyse Payment Risk
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Step 2: Risk Result */}
      {result && riskConfig && (
        <div className="space-y-4 animate-fade-in-up">
          {/* Risk Score Card */}
          <Card className={cn('rounded-2xl border-0 shadow-xl overflow-hidden')}>
            {/* Gradient header */}
            <div className={cn('h-2 bg-gradient-to-r', riskConfig.gradient)} />
            <CardContent className="pt-8 pb-6 space-y-6">
              {/* Gauge */}
              <div className="flex justify-center">
                <div className="risk-gauge-container">
                  <RiskScoreGauge score={result.risk_score} level={result.risk_level} size="lg" />
                </div>
              </div>

              {/* Risk level badge + context */}
              <div className={cn('rounded-xl p-4 text-center', riskConfig.bg, riskConfig.border, 'border')}>
                <div className={cn('inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-sm font-bold mb-2', riskConfig.badge)}>
                  <riskConfig.icon className="h-4 w-4" />
                  {riskConfig.label}
                </div>
                <p className={cn('text-sm font-medium', riskConfig.text)}>{riskConfig.message}</p>
                {result.recommended_action && (
                  <p className="text-xs text-muted-foreground mt-1">
                    Recommended: {result.recommended_action}
                  </p>
                )}
              </div>

              {/* AI Explanation */}
              {aiLoading ? (
                <div className="rounded-xl bg-primary/5 border border-primary/10 p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Bot className="h-4 w-4 text-primary animate-pulse" />
                    <p className="text-sm font-semibold text-primary">AI is analysing...</p>
                  </div>
                  <div className="space-y-2">
                    <div className="h-3 rounded shimmer" />
                    <div className="h-3 w-4/5 rounded shimmer" />
                  </div>
                </div>
              ) : explanation ? (
                <div className="rounded-xl bg-gradient-to-br from-primary/5 to-primary/10 border border-primary/15 p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Bot className="h-4 w-4 text-primary" />
                    <p className="text-sm font-bold text-primary">AI Explanation</p>
                  </div>
                  <p className="text-sm text-foreground leading-relaxed">{explanation}</p>
                  {recommendation && (
                    <div className="mt-3 flex items-center gap-2 pt-3 border-t border-primary/10">
                      <ArrowRight className="h-3.5 w-3.5 text-primary flex-shrink-0" />
                      <p className="text-xs font-semibold text-primary">{recommendation}</p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="rounded-xl bg-gray-50 border p-4">
                  <p className="text-sm text-muted-foreground">AI explanation unavailable. Showing structured risk signals below.</p>
                </div>
              )}

              {/* Risk Reasons */}
              {result.reasons.length > 0 && (
                <div>
                  <p className="text-sm font-bold mb-3 text-foreground">Why this was flagged</p>
                  <div className="space-y-2">
                    {result.reasons.map((r) => (
                      <div
                        key={r.signal_name}
                        className={cn(
                          'flex items-start gap-3 rounded-xl p-3 text-sm',
                          r.severity === 'HIGH' ? 'bg-red-50 border border-red-100' :
                          r.severity === 'MEDIUM' ? 'bg-amber-50 border border-amber-100' :
                          'bg-gray-50 border border-gray-100',
                        )}
                      >
                        <span className={cn(
                          'mt-0.5 h-2 w-2 rounded-full flex-shrink-0',
                          r.severity === 'HIGH' ? 'bg-red-500' :
                          r.severity === 'MEDIUM' ? 'bg-amber-500' : 'bg-gray-400',
                        )} />
                        <div className="flex-1">
                          <span className={cn(
                            'font-medium text-xs uppercase tracking-wide',
                            r.severity === 'HIGH' ? 'text-red-600' :
                            r.severity === 'MEDIUM' ? 'text-amber-600' : 'text-gray-500',
                          )}>
                            {r.severity}
                          </span>
                          <p className="text-foreground mt-0.5">{r.reason}</p>
                        </div>
                        <span className="text-xs text-muted-foreground font-mono">+{r.score_impact}pts</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {result.reasons.length === 0 && (
                <div className="rounded-xl bg-emerald-50 border border-emerald-100 p-4 flex items-center gap-3">
                  <CheckCircle className="h-4 w-4 text-emerald-600 flex-shrink-0" />
                  <p className="text-sm text-emerald-800">No specific risk signals detected. Payment appears normal.</p>
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex gap-3 pt-2">
                <Button variant="outline" className="flex-1 h-11" onClick={onCancel}>
                  <X className="h-4 w-4" />
                  Cancel
                </Button>
                <Button
                  className={cn(
                    'flex-1 h-11 font-semibold',
                    result.risk_level === 'HIGH' ? 'bg-red-600 hover:bg-red-700 text-white' :
                    result.risk_level === 'MEDIUM' ? 'bg-amber-500 hover:bg-amber-600 text-white' :
                    'btn-primary-gradient',
                  )}
                  onClick={onContinue}
                  loading={processing}
                >
                  <ArrowRight className="h-4 w-4" />
                  {riskConfig.buttonLabel}
                </Button>
              </div>

              {result.risk_level === 'HIGH' && (
                <p className="text-center text-xs text-red-600 font-medium">
                  ⚠ You are overriding a HIGH RISK warning. Verify the recipient's identity before proceeding.
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}