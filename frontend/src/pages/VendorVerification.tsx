import { useState } from 'react'
import { ShieldCheck, ShieldAlert, Search, AlertCircle, CheckCircle2, Hash, IndianRupee, Phone } from 'lucide-react'
import { vendorApi } from '../features/vendor/vendorService'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Label } from '../components/ui/Label'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card'
import { Alert } from '../components/ui/Alert'
import type { PaymentVerificationResult } from '../types'
import { formatINR } from '../lib/utils'
import { cn } from '../lib/utils'

export default function VendorVerification() {
  const [paymentId, setPaymentId] = useState('')
  const [amount, setAmount] = useState('')
  const [customerPhone, setCustomerPhone] = useState('')
  const [verifying, setVerifying] = useState(false)
  const [result, setResult] = useState<PaymentVerificationResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleVerify(e: React.FormEvent) {
    e.preventDefault()
    setVerifying(true)
    setError(null)
    setResult(null)
    try {
      const res = await vendorApi.verifyByDetails({
        payment_id: paymentId || undefined,
        amount: amount ? Number(amount) * 100 : undefined,
        customer_phone: customerPhone || undefined,
      })
      setResult(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Verification failed. Please try again.')
    } finally {
      setVerifying(false)
    }
  }

  function handleReset() {
    setResult(null)
    setPaymentId('')
    setAmount('')
    setCustomerPhone('')
    setError(null)
  }

  return (
    <div className="mx-auto max-w-xl space-y-6 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Payment Verification</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Verify customer payment claims against trusted Razorpay records — not screenshots.
        </p>
      </div>

      {/* Critical Principle Banner */}
      <div className="rounded-xl bg-amber-50 border border-amber-200 p-4 flex items-start gap-3">
        <AlertCircle className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-semibold text-amber-800">Never trust a screenshot as payment proof</p>
          <p className="text-xs text-amber-700 mt-0.5">
            Only a verified payment from our trusted records confirms actual payment.
          </p>
        </div>
      </div>

      {error && <Alert variant="error">{error}</Alert>}

      {/* Verification Form */}
      {!result && (
        <Card className="rounded-2xl border-0 shadow-md animate-fade-in-up">
          <CardHeader className="pb-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
                <ShieldCheck className="h-5 w-5 text-primary" />
              </div>
              <div>
                <CardTitle>Customer Claims Payment</CardTitle>
                <CardDescription>Enter the details shown by the customer</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleVerify} className="space-y-5">
              <div className="space-y-2">
                <Label htmlFor="payment_id" className="font-semibold text-sm flex items-center gap-2">
                  <Hash className="h-3.5 w-3.5 text-muted-foreground" />
                  Razorpay Payment ID
                </Label>
                <Input
                  id="payment_id"
                  value={paymentId}
                  onChange={(e) => setPaymentId(e.target.value)}
                  placeholder="pay_XXXXXXXXXXXXXXXX"
                  className="font-mono text-sm"
                />
                <p className="text-xs text-muted-foreground">Starts with "pay_" — most reliable verification method</p>
              </div>

              <div className="flex items-center gap-3">
                <div className="flex-1 border-t" />
                <span className="text-xs text-muted-foreground font-medium">OR</span>
                <div className="flex-1 border-t" />
              </div>

              <div className="space-y-2">
                <Label htmlFor="amount" className="font-semibold text-sm flex items-center gap-2">
                  <IndianRupee className="h-3.5 w-3.5 text-muted-foreground" />
                  Claimed Amount (₹)
                </Label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">₹</span>
                  <Input
                    id="amount"
                    type="number"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    placeholder="850"
                    className="pl-7"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="customer_phone" className="font-semibold text-sm flex items-center gap-2">
                  <Phone className="h-3.5 w-3.5 text-muted-foreground" />
                  Customer Phone (optional)
                </Label>
                <Input
                  id="customer_phone"
                  value={customerPhone}
                  onChange={(e) => setCustomerPhone(e.target.value)}
                  placeholder="9876543210"
                />
              </div>

              <Button
                type="submit"
                className="w-full h-12 text-base font-semibold btn-primary-gradient"
                loading={verifying}
                disabled={!paymentId && !amount}
              >
                <Search className="h-5 w-5" />
                Verify Payment
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Verification Result */}
      {result && (
        <div className="space-y-4 animate-fade-in-up">
          {result.verified ? (
            <div className="verify-success">
              <div className="flex items-center gap-4 mb-5">
                <div className="flex h-14 w-14 flex-shrink-0 items-center justify-center rounded-2xl bg-emerald-100">
                  <CheckCircle2 className="h-8 w-8 text-emerald-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-emerald-900">✅ PAYMENT VERIFIED</p>
                  <p className="text-sm text-emerald-700 mt-0.5">You can safely release the order.</p>
                </div>
              </div>

              {/* Payment Details Grid */}
              <div className="grid grid-cols-2 gap-4 rounded-xl bg-white/60 border border-emerald-200 p-4">
                {result.amount != null && (
                  <div>
                    <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">Amount</p>
                    <p className="text-xl font-bold text-emerald-800 mt-0.5">{formatINR(result.amount)}</p>
                  </div>
                )}
                {result.status && (
                  <div>
                    <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">Status</p>
                    <p className="font-semibold text-emerald-800 capitalize mt-0.5">{result.status}</p>
                  </div>
                )}
                {result.payment_id && (
                  <div className="col-span-2">
                    <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">Payment ID</p>
                    <p className="font-mono text-sm text-foreground mt-0.5 break-all">{result.payment_id}</p>
                  </div>
                )}
                {result.risk_level && (
                  <div>
                    <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">Risk Level</p>
                    <p className={cn('font-bold mt-0.5', {
                      'text-emerald-600': result.risk_level === 'LOW',
                      'text-amber-600': result.risk_level === 'MEDIUM',
                      'text-red-600': result.risk_level === 'HIGH',
                    })}>{result.risk_level}</p>
                  </div>
                )}
              </div>

              <div className="mt-4 rounded-xl bg-emerald-100 px-4 py-3 text-center">
                <p className="text-sm font-bold text-emerald-900">Safe to release order ✓</p>
              </div>
            </div>
          ) : (
            <div className="verify-fail">
              <div className="flex items-center gap-4 mb-5">
                <div className="flex h-14 w-14 flex-shrink-0 items-center justify-center rounded-2xl bg-red-100">
                  <ShieldAlert className="h-8 w-8 text-red-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-red-900">🔴 NOT VERIFIED</p>
                  <p className="text-sm text-red-700 mt-0.5">No matching confirmed payment found.</p>
                </div>
              </div>

              {result.amount != null && (
                <div className="rounded-xl bg-white/60 border border-red-200 p-4 mb-4">
                  <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">Claimed Amount</p>
                  <p className="text-xl font-bold text-red-800 mt-0.5">{formatINR(result.amount)}</p>
                  <p className="text-sm text-red-700 mt-1">{result.message}</p>
                </div>
              )}

              <div className="rounded-xl bg-red-100 border border-red-300 px-4 py-4">
                <p className="text-base font-bold text-red-900 text-center">🚫 DO NOT RELEASE THE ORDER</p>
                <p className="text-xs text-red-800 text-center mt-1">
                  Ask the customer to share the Razorpay payment ID for verification.
                </p>
              </div>
            </div>
          )}

          <Button variant="outline" className="w-full" onClick={handleReset}>
            Verify Another Payment
          </Button>
        </div>
      )}
    </div>
  )
}