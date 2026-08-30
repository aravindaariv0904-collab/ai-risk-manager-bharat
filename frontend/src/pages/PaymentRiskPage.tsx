import { useState, useEffect, useRef } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import {
  ShieldCheck, ArrowRight, X, Bot, AlertTriangle, CheckCircle, Info,
  Phone, QrCode, Store, Search, Sparkles, Check, Upload, Camera, VideoOff
} from 'lucide-react'
import jsQR from 'jsqr'
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
  merchant_id: z.string().min(1, 'Please identify or select a merchant'),
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

type IdentifyTab = 'phone' | 'qr' | 'select'

export default function PaymentRiskPage() {
  const [identifyTab, setIdentifyTab] = useState<IdentifyTab>('qr')
  const [phoneInput, setPhoneInput] = useState('')
  const [qrInput, setQrInput] = useState('')
  const [searchingMerchant, setSearchingMerchant] = useState(false)
  const [lookupMessage, setLookupMessage] = useState<string | null>(null)

  // Camera QR Scanner State
  const [isCameraActive, setIsCameraActive] = useState(false)
  const [cameraError, setCameraError] = useState<string | null>(null)
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const animFrameRef = useRef<number | null>(null)

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
    setValue,
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
      .then((data) => {
        setMerchants(data)
        if (data.length > 0 && !merchantId) {
          setSelectedMerchant(data[0])
          setValue('merchant_id', data[0].id)
        }
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoadingMerchants(false))
  }, [])

  useEffect(() => {
    if (merchantId && merchants.length) {
      const match = merchants.find((m) => m.id === merchantId)
      if (match) setSelectedMerchant(match)
    }
  }, [merchantId, merchants])

  // Camera cleanup on unmount or tab switch
  useEffect(() => {
    return () => {
      stopCamera()
    }
  }, [])

  // Auto-bind stream to video element when camera becomes active
  useEffect(() => {
    if (isCameraActive && streamRef.current && videoRef.current) {
      videoRef.current.srcObject = streamRef.current
      videoRef.current.setAttribute('playsinline', 'true')
      videoRef.current.play().then(() => {
        requestScanFrame()
      }).catch((err) => {
        console.error('Video play error:', err)
      })
    }
  }, [isCameraActive])

  function stopCamera() {
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current)
      animFrameRef.current = null
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop())
      streamRef.current = null
    }
    setIsCameraActive(false)
  }

  async function startCamera() {
    setCameraError(null)
    stopCamera()

    try {
      let stream: MediaStream
      try {
        // Try back / environment camera first
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } },
          audio: false,
        })
      } catch {
        // Fallback to default / front webcam
        stream = await navigator.mediaDevices.getUserMedia({
          video: true,
          audio: false,
        })
      }

      streamRef.current = stream
      setIsCameraActive(true)
    } catch (err: any) {
      console.error('Camera access error:', err)
      setCameraError(err.message || 'Unable to access camera. Please allow camera permissions in your browser.')
      setIsCameraActive(false)
    }
  }

  function requestScanFrame() {
    if (!videoRef.current || !canvasRef.current) return

    const video = videoRef.current
    const canvas = canvasRef.current

    if (video.readyState >= video.HAVE_CURRENT_DATA) {
      const ctx = canvas.getContext('2d', { willReadFrequently: true })
      if (ctx && video.videoWidth > 0 && video.videoHeight > 0) {
        canvas.width = video.videoWidth
        canvas.height = video.videoHeight
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height)
        const code = jsQR(imageData.data, imageData.width, imageData.height, {
          inversionAttempts: 'attemptBoth',
        })

        if (code && code.data && code.data.trim().length > 0) {
          stopCamera()
          handleQrLookup(code.data)
          return
        }
      }
    }

    animFrameRef.current = requestAnimationFrame(requestScanFrame)
  }

  // Handle uploaded image file scan
  function handleImageUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return

    const reader = new FileReader()
    reader.onload = (event) => {
      const img = new Image()
      img.onload = () => {
        const canvas = document.createElement('canvas')
        canvas.width = img.width
        canvas.height = img.height
        const ctx = canvas.getContext('2d')
        if (ctx) {
          ctx.drawImage(img, 0, 0)
          const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height)
          const code = jsQR(imageData.data, imageData.width, imageData.height)
          if (code && code.data) {
            handleQrLookup(code.data)
          } else {
            setLookupMessage('No QR code detected in the uploaded image.')
          }
        }
      }
      img.src = event.target?.result as string
    }
    reader.readAsDataURL(file)
  }

  // Handle phone lookup
  async function handlePhoneLookup(rawPhone: string) {
    setPhoneInput(rawPhone)
    setLookupMessage(null)
    const cleaned = rawPhone.replace(/\D/g, '')
    if (cleaned.length >= 10) {
      setSearchingMerchant(true)
      try {
        const found = await merchantsApi.lookup({ phone: cleaned })
        if (found) {
          setSelectedMerchant(found)
          setValue('merchant_id', found.id)
          setLookupMessage(`✓ Identified: ${found.business_name}`)
        } else {
          const localMatch = merchants.find((m) => m.business_name.toLowerCase().includes(rawPhone.toLowerCase()))
          if (localMatch) {
            setSelectedMerchant(localMatch)
            setValue('merchant_id', localMatch.id)
            setLookupMessage(`✓ Identified: ${localMatch.business_name}`)
          } else {
            setLookupMessage('No merchant registered with this number. Selecting nearest match.')
          }
        }
      } catch (err) {
        console.error('Phone lookup failed', err)
      } finally {
        setSearchingMerchant(false)
      }
    }
  }

  // Handle QR / UPI lookup
  async function handleQrLookup(rawQr: string) {
    setQrInput(rawQr)
    setLookupMessage(null)
    if (rawQr.trim().length >= 3) {
      setSearchingMerchant(true)
      try {
        if (rawQr.includes('am=')) {
          const match = rawQr.match(/am=([0-9.]+)/)
          if (match && match[1]) {
            const amt = Math.round(parseFloat(match[1]))
            if (amt > 0) setValue('amount', amt)
          }
        }

        const found = await merchantsApi.lookup({ q: rawQr })
        if (found) {
          setSelectedMerchant(found)
          setValue('merchant_id', found.id)
          setLookupMessage(`✓ Scanned & Verified: ${found.business_name}`)
        } else {
          const term = rawQr.toLowerCase()
          const localMatch = merchants.find((m) =>
            m.business_name.toLowerCase().includes(term) || term.includes(m.business_name.toLowerCase().split(' ')[0])
          )
          if (localMatch) {
            setSelectedMerchant(localMatch)
            setValue('merchant_id', localMatch.id)
            setLookupMessage(`✓ Identified: ${localMatch.business_name}`)
          } else if (merchants.length > 0) {
            setSelectedMerchant(merchants[0])
            setValue('merchant_id', merchants[0].id)
            setLookupMessage(`✓ Matched to ${merchants[0].business_name}`)
          }
        }
      } catch (err) {
        console.error('QR lookup error', err)
      } finally {
        setSearchingMerchant(false)
      }
    }
  }

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
    if (!result || !selectedMerchant) return
    setProcessing(true)
    setError(null)
    try {
      const order = await paymentsApi.createOrder({
        amount: amount * 100,
        merchant_id: selectedMerchant.id,
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
        <Card className="rounded-2xl border-0 shadow-md animate-fade-in-up overflow-hidden">
          <CardHeader className="pb-4 border-b bg-slate-50/50">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
                  <ShieldCheck className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <CardTitle>Identify Merchant & Pay</CardTitle>
                  <CardDescription>Instant merchant recognition & pre-payment risk analysis</CardDescription>
                </div>
              </div>
            </div>

            {/* Identification Mode Tabs */}
            <div className="mt-4 grid grid-cols-3 gap-1 rounded-xl bg-slate-100 p-1">
              <button
                type="button"
                onClick={() => setIdentifyTab('phone')}
                className={cn(
                  'flex items-center justify-center gap-1.5 rounded-lg py-2 text-xs font-semibold transition-all',
                  identifyTab === 'phone' ? 'bg-white text-primary shadow-sm' : 'text-muted-foreground hover:text-foreground'
                )}
              >
                <Phone className="h-3.5 w-3.5" />
                Mobile No.
              </button>
              <button
                type="button"
                onClick={() => setIdentifyTab('qr')}
                className={cn(
                  'flex items-center justify-center gap-1.5 rounded-lg py-2 text-xs font-semibold transition-all',
                  identifyTab === 'qr' ? 'bg-white text-primary shadow-sm' : 'text-muted-foreground hover:text-foreground'
                )}
              >
                <QrCode className="h-3.5 w-3.5" />
                QR / UPI
              </button>
              <button
                type="button"
                onClick={() => setIdentifyTab('select')}
                className={cn(
                  'flex items-center justify-center gap-1.5 rounded-lg py-2 text-xs font-semibold transition-all',
                  identifyTab === 'select' ? 'bg-white text-primary shadow-sm' : 'text-muted-foreground hover:text-foreground'
                )}
              >
                <Store className="h-3.5 w-3.5" />
                Directory
              </button>
            </div>
          </CardHeader>

          <CardContent className="pt-6">
            <form onSubmit={handleSubmit(onPrecheck)} className="space-y-5">
              
              {/* Tab 1: Phone Search */}
              {identifyTab === 'phone' && (
                <div className="space-y-2 animate-fade-in">
                  <Label htmlFor="phone_input" className="font-semibold text-sm flex items-center justify-between">
                    <span>Merchant Mobile Number</span>
                    <span className="text-[11px] text-muted-foreground font-normal">Auto-detects merchant</span>
                  </Label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground font-semibold text-sm">+91</span>
                    <Input
                      id="phone_input"
                      type="tel"
                      value={phoneInput}
                      onChange={(e) => handlePhoneLookup(e.target.value)}
                      placeholder="e.g. 9812345670"
                      className="pl-12 h-11"
                    />
                    {searchingMerchant && (
                      <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-primary animate-pulse">
                        Searching...
                      </span>
                    )}
                  </div>
                  {lookupMessage && (
                    <p className="text-xs font-medium text-emerald-600 animate-fade-in">{lookupMessage}</p>
                  )}
                </div>
              )}

              {/* Tab 2: QR / UPI Input with Live Camera Scanner */}
              {identifyTab === 'qr' && (
                <div className="space-y-4 animate-fade-in">
                  
                  {/* Camera Scanner Viewfinder */}
                  {isCameraActive ? (
                    <div className="relative overflow-hidden rounded-2xl bg-black aspect-video flex flex-col items-center justify-center border-2 border-primary/40 shadow-inner">
                      <video
                        ref={videoRef}
                        className="w-full h-full object-cover"
                        playsInline
                        muted
                        autoPlay
                      />
                      <canvas ref={canvasRef} className="hidden" />

                      {/* Scanner target overlay box */}
                      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                        <div className="relative w-48 h-48 border-2 border-emerald-400/80 rounded-2xl flex items-center justify-center">
                          {/* Corner accents */}
                          <span className="absolute -top-1 -left-1 w-4 h-4 border-t-4 border-l-4 border-emerald-400 rounded-tl" />
                          <span className="absolute -top-1 -right-1 w-4 h-4 border-t-4 border-r-4 border-emerald-400 rounded-tr" />
                          <span className="absolute -bottom-1 -left-1 w-4 h-4 border-b-4 border-l-4 border-emerald-400 rounded-bl" />
                          <span className="absolute -bottom-1 -right-1 w-4 h-4 border-b-4 border-r-4 border-emerald-400 rounded-br" />
                          
                          {/* Laser scanning line */}
                          <div className="w-full h-0.5 bg-gradient-to-r from-transparent via-emerald-400 to-transparent shadow-[0_0_8px_#34d399] animate-pulse" />
                        </div>
                      </div>

                      {/* Camera control overlay bar */}
                      <div className="absolute bottom-3 left-3 right-3 flex items-center justify-between bg-black/60 backdrop-blur-md rounded-xl p-2 px-3 text-white">
                        <span className="text-xs font-medium flex items-center gap-1.5">
                          <span className="h-2 w-2 rounded-full bg-emerald-400 animate-ping" />
                          Align QR code within frame
                        </span>
                        <Button
                          type="button"
                          variant="destructive"
                          size="sm"
                          onClick={stopCamera}
                          className="h-7 text-xs px-2.5"
                        >
                          <VideoOff className="h-3.5 w-3.5 mr-1" />
                          Stop
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <div className="grid grid-cols-2 gap-2">
                      <Button
                        type="button"
                        variant="outline"
                        onClick={startCamera}
                        className="h-14 flex flex-col items-center justify-center gap-1 border-primary/20 hover:border-primary/50 hover:bg-primary/5 group"
                      >
                        <Camera className="h-5 w-5 text-primary group-hover:scale-110 transition-transform" />
                        <span className="text-xs font-bold text-foreground">Open Camera Scanner</span>
                      </Button>

                      <label className="h-14 flex flex-col items-center justify-center gap-1 rounded-xl border border-slate-200 hover:border-slate-300 hover:bg-slate-50 cursor-pointer text-center transition-colors">
                        <Upload className="h-5 w-5 text-muted-foreground" />
                        <span className="text-xs font-semibold text-muted-foreground">Upload QR Image</span>
                        <input
                          type="file"
                          accept="image/*"
                          onChange={handleImageUpload}
                          className="hidden"
                        />
                      </label>
                    </div>
                  )}

                  {cameraError && (
                    <Alert variant="error" className="py-2 text-xs">
                      {cameraError}
                    </Alert>
                  )}

                  {/* Manual UPI Text input & Sample QR */}
                  <div className="space-y-1.5">
                    <Label htmlFor="qr_input" className="font-semibold text-xs text-muted-foreground flex items-center justify-between">
                      <span>Or Enter UPI ID / QR String</span>
                      <span className="text-[11px] font-normal">Extracts name & amount</span>
                    </Label>
                    <div className="relative">
                      <Input
                        id="qr_input"
                        value={qrInput}
                        onChange={(e) => handleQrLookup(e.target.value)}
                        placeholder="upi://pay?pa=ramesh@upi&pn=RameshStore&am=250"
                        className="h-10 pr-24 text-xs font-mono"
                      />
                      <button
                        type="button"
                        onClick={() => handleQrLookup('upi://pay?pa=ramesh@upi&pn=Ramesh%20General%20Store&am=350')}
                        className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-md bg-primary/10 px-2 py-1 text-[10px] font-semibold text-primary hover:bg-primary/20"
                      >
                        Sample QR
                      </button>
                    </div>
                  </div>

                  {lookupMessage && (
                    <p className="text-xs font-medium text-emerald-600 animate-fade-in">{lookupMessage}</p>
                  )}
                </div>
              )}

              {/* Tab 3: Directory Select */}
              {identifyTab === 'select' && (
                <div className="space-y-2 animate-fade-in">
                  <Label htmlFor="merchant_id" className="font-semibold text-sm">Select Registered Merchant</Label>
                  <Select
                    id="merchant_id"
                    disabled={loadingMerchants}
                    className="h-11"
                    {...register('merchant_id')}
                  >
                    <option value="">{loadingMerchants ? 'Loading merchants...' : 'Select a merchant'}</option>
                    {merchants.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.business_name}{m.business_category ? ` (${m.business_category})` : ''}
                      </option>
                    ))}
                  </Select>
                </div>
              )}

              {/* Verified Merchant Identification Card */}
              {selectedMerchant ? (
                <div className="rounded-xl bg-gradient-to-r from-emerald-50/80 to-teal-50/80 border border-emerald-200 p-4 animate-fade-in">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-100 text-emerald-700">
                        <Store className="h-5 w-5" />
                      </div>
                      <div>
                        <div className="flex items-center gap-1.5">
                          <p className="font-bold text-sm text-emerald-950">{selectedMerchant.business_name}</p>
                          <span className="inline-flex items-center gap-0.5 rounded-full bg-emerald-200/60 px-2 py-0.5 text-[10px] font-bold text-emerald-800">
                            <ShieldCheck className="h-3 w-3 text-emerald-600" />
                            Verified
                          </span>
                        </div>
                        <p className="text-xs text-emerald-700 capitalize">
                          {selectedMerchant.business_category || 'Retail Store'} · Bharat Protected
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="rounded-xl border border-dashed border-slate-200 p-4 text-center">
                  <p className="text-xs text-muted-foreground">Identify a merchant via Mobile, QR, or Directory above</p>
                </div>
              )}

              {errors.merchant_id && <p className="text-sm text-red-600">{errors.merchant_id.message}</p>}

              {/* Amount Input */}
              <div className="space-y-2">
                <Label htmlFor="amount" className="font-semibold text-sm">Payment Amount (₹)</Label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground font-semibold text-base">₹</span>
                  <Input
                    id="amount"
                    type="number"
                    inputMode="numeric"
                    min={1}
                    placeholder="250"
                    className="pl-8 text-lg font-bold h-12"
                    {...register('amount')}
                  />
                </div>
                {errors.amount && <p className="text-sm text-red-600">{errors.amount.message}</p>}
              </div>

              {/* Total summary before check */}
              {selectedMerchant && amount > 0 && (
                <div className="rounded-xl bg-slate-50 border p-3.5 flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Paying to <strong className="text-foreground">{selectedMerchant.business_name}</strong></span>
                  <span className="font-bold text-sm text-primary">{formatINR(amount * 100)}</span>
                </div>
              )}

              <Button
                type="submit"
                className="w-full h-12 text-base font-semibold btn-primary-gradient"
                loading={checking}
                disabled={loadingMerchants || !selectedMerchant}
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