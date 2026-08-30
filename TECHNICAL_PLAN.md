# Technical Plan — AI Risk Manager for Bharat

## 1. Final Product Definition

**AI Risk Manager for Bharat's Everyday Digital Payments** — A two-sided AI-powered payment safety platform for citizens and micro-merchants (street vendors, small shops, food stalls, home businesses, local service providers) that adds real-time risk scoring, explainable fraud detection, and payment verification on top of Razorpay payment infrastructure.

**Core Innovation**: Real-time risk scoring + explainable AI + payment verification + two-sided protection for payer and merchant.

**Core Flow**: Detect → Score → Explain → Verify → Act → Learn

---

## 2. Final User Journeys

### Citizen Journey (Flow A)
1. Citizen logs in → Dashboard shows spending, alerts, recent transactions
2. Citizen initiates payment to vendor → Enters amount, selects merchant
3. **Risk Pre-check** runs before payment → Risk engine analyzes transaction
4. System returns: risk_score (0-100), risk_level (LOW/MEDIUM/HIGH), structured reasons, recommended_action
5. **AI Explanation** (Gemini) converts structured reasons to natural language in user's language
6. Citizen sees risk screen → Continues or cancels
7. If continues → Razorpay payment flow → Webhook confirms → Transaction recorded

### Vendor Journey (Flow B)
1. Vendor logs in → Dashboard shows collections, successful/pending payments, suspicious claims
2. Customer claims "I paid ₹X" → Vendor enters payment ID or amount/customer
3. **Payment Verification** queries Razorpay/webhook events for matching successful payment
4. Result: ✅ VERIFIED (payment_id, status, amount) or 🔴 NOT VERIFIED (no match found)
5. Vendor sees clear action: "Release order" or "Do not release order"
6. Risk alerts surface high-risk payment claims automatically

---

## 3. Locked Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18 + TypeScript + Vite |
| Styling | Tailwind CSS + shadcn/ui |
| Charts | Recharts |
| Routing | React Router v6 |
| Forms | React Hook Form + Zod |
| Backend | Python 3.11 + FastAPI |
| Validation | Pydantic v2 |
| HTTP Client | httpx |
| Database | Supabase (PostgreSQL) |
| Auth | Supabase Auth |
| Security | Supabase RLS |
| Realtime | Supabase Realtime (notifications) |
| Payments | Razorpay Orders API, Payments API, Webhooks |
| AI/ML | scikit-learn (Isolation Forest, rule engine) + Gemini API |
| Deployment | Frontend: Vercel, Backend: Render, DB: Supabase |

---

## 4. Architecture

```
┌──────────────────┐     ┌──────────────────┐
│  CITIZEN APP     │     │  VENDOR APP      │
│  React + TS      │     │  React + TS      │
└────────┬─────────┘     └────────┬─────────┘
         │                        │
         └───────────┬────────────┘
                     ▼
          ┌──────────────────────┐
          │   FASTAPI BACKEND    │
          └──────────┬───────────┘
                     │
      ┌──────────────┼──────────────┐
      ▼              ▼              ▼
┌────────────┐ ┌───────────┐ ┌────────────┐
│ Razorpay   │ │ Risk      │ │ User       │
│ Service    │ │ Service   │ │ Service    │
│ Orders/    │ │ Rules +   │ │ Profiles/  │
│ Payments/  │ │ ML +      │ │ History    │
│ Webhooks   │ │ Behavior  │ │            │
└─────┬──────┘ └─────┬─────┘ └────────────┘
      │              │
      │              ▼
      │       Risk Score 0-100
      │              │
      │              ▼
      │       Policy Engine
      │              │
      │              ▼
      │       LOW/MED/HIGH
      │              │
      │              ▼
      │       Gemini AI Layer
      │              │
      │              ▼
      │       Explanation
      │
      ▼
┌──────────────────┐
│ Webhook Processor│
│ Signature Verify │
│ Idempotency      │
│ Event Persistence│
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Supabase/Postgres│
│ RLS Enabled      │
└──────────────────┘
```

---

## 5. Database Schema

### Core Tables

```sql
-- users (extends Supabase auth.users)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_user_id UUID UNIQUE NOT NULL REFERENCES auth.users(id),
    name TEXT NOT NULL,
    phone TEXT,
    role TEXT NOT NULL CHECK (role IN ('citizen', 'merchant', 'admin')),
    language TEXT DEFAULT 'en' CHECK (language IN ('en', 'hi', 'ta')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- merchants
CREATE TABLE merchants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE NOT NULL REFERENCES users(id),
    business_name TEXT NOT NULL,
    business_category TEXT,
    risk_profile JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- transactions
CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    razorpay_payment_id TEXT UNIQUE,
    razorpay_order_id TEXT,
    payer_id UUID NOT NULL REFERENCES users(id),
    merchant_id UUID NOT NULL REFERENCES merchants(id),
    amount INTEGER NOT NULL, -- in paise
    currency TEXT DEFAULT 'INR',
    status TEXT NOT NULL CHECK (status IN ('created', 'pending', 'captured', 'failed', 'refunded')),
    risk_score INTEGER CHECK (risk_score BETWEEN 0 AND 100),
    risk_level TEXT CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH')),
    risk_action TEXT CHECK (risk_action IN ('ALLOW', 'VERIFY', 'WARN', 'BLOCK')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- risk_events (individual signals)
CREATE TABLE risk_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL REFERENCES transactions(id),
    signal_name TEXT NOT NULL,
    signal_value JSONB,
    severity TEXT CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH')),
    score_impact INTEGER,
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- risk_decisions (aggregated decision)
CREATE TABLE risk_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL REFERENCES transactions(id),
    score INTEGER NOT NULL CHECK (score BETWEEN 0 AND 100),
    level TEXT NOT NULL CHECK (level IN ('LOW', 'MEDIUM', 'HIGH')),
    action TEXT NOT NULL CHECK (action IN ('ALLOW', 'VERIFY', 'WARN', 'BLOCK')),
    explanation TEXT,
    model_version TEXT DEFAULT 'v1.0',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- webhook_events (idempotency + audit)
CREATE TABLE webhook_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id TEXT UNIQUE NOT NULL,
    event_type TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    processing_status TEXT DEFAULT 'pending' CHECK (processing_status IN ('pending', 'processed', 'failed', 'duplicate')),
    received_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);

-- feedback (for model improvement)
CREATE TABLE feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL REFERENCES transactions(id),
    label TEXT CHECK (label IN ('legitimate', 'suspicious', 'fraud')),
    fraud_confirmed BOOLEAN,
    user_feedback TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_transactions_payer ON transactions(payer_id);
CREATE INDEX idx_transactions_merchant ON transactions(merchant_id);
CREATE INDEX idx_transactions_created ON transactions(created_at DESC);
CREATE INDEX idx_risk_events_transaction ON risk_events(transaction_id);
CREATE INDEX idx_webhook_events_event_id ON webhook_events(event_id);
CREATE INDEX idx_webhook_events_status ON webhook_events(processing_status);
```

### RLS Policies

```sql
-- Users see only their own data
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users see own profile" ON users FOR SELECT USING (auth.uid() = auth_user_id);

-- Merchants see their own merchant record
ALTER TABLE merchants ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Merchant sees own record" ON merchants FOR SELECT USING (user_id IN (SELECT id FROM users WHERE auth_user_id = auth.uid()));

-- Transactions: payer sees their payments, merchant sees their collections
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Payer sees own transactions" ON transactions FOR SELECT USING (payer_id IN (SELECT id FROM users WHERE auth_user_id = auth.uid()));
CREATE POLICY "Merchant sees own transactions" ON transactions FOR SELECT USING (merchant_id IN (SELECT id FROM merchants WHERE user_id IN (SELECT id FROM users WHERE auth_user_id = auth.uid())));

-- Risk events/decisions follow transaction visibility
ALTER TABLE risk_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Risk events follow transaction" ON risk_events FOR SELECT USING (transaction_id IN (SELECT id FROM transactions WHERE payer_id IN (SELECT id FROM users WHERE auth_user_id = auth.uid()) OR merchant_id IN (SELECT id FROM merchants WHERE user_id IN (SELECT id FROM users WHERE auth_user_id = auth.uid()))));

ALTER TABLE risk_decisions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Risk decisions follow transaction" ON risk_decisions FOR SELECT USING (transaction_id IN (SELECT id FROM transactions WHERE payer_id IN (SELECT id FROM users WHERE auth_user_id = auth.uid()) OR merchant_id IN (SELECT id FROM merchants WHERE user_id IN (SELECT id FROM users WHERE auth_user_id = auth.uid()))));
```

---

## 6. API Contract

### Risk APIs
```
POST   /api/risk/precheck
  Request: { amount, currency, merchant_id, payer_id }
  Response: { risk_score, risk_level, risk_action, reasons[], recommended_action, transaction_id }

GET    /api/risk/{transaction_id}
  Response: { risk_score, risk_level, risk_action, reasons[], explanation, model_version }
```

### Payment APIs
```
POST   /api/payments/create-order
  Request: { amount, currency, merchant_id, payer_id }
  Response: { order_id, amount, currency, key_id }

GET    /api/payments/{payment_id}/status
  Response: { payment_id, status, amount, captured_at }
```

### Webhook
```
POST   /api/webhooks/razorpay
  Headers: X-Razorpay-Signature
  Body: Razorpay webhook payload
  Response: { received: true }
```

### Vendor APIs
```
GET    /api/vendor/dashboard
  Response: { today_collections, successful_count, pending_count, suspicious_claims[], risk_alerts[] }

GET    /api/vendor/payments
  Query: status, date_from, date_to, limit, offset
  Response: { payments[], total }

GET    /api/vendor/payment-verification/{payment_id}
  Response: { verified: boolean, payment_id, amount, status, captured_at, risk_level }
```

### AI APIs
```
POST   /api/ai/explain-risk
  Request: { risk_score, risk_level, reasons[], language }
  Response: { explanation, recommendation }

POST   /api/ai/assistant
  Request: { query, user_id, context }
  Response: { answer, data_sources[] }
```

### Feedback
```
POST   /api/feedback
  Request: { transaction_id, label, fraud_confirmed, user_feedback }
  Response: { success: true }
```

---

## 7. Razorpay Integration Points

| Feature | Razorpay API/Event |
|---------|-------------------|
| Create Order | `POST /v1/orders` |
| Fetch Payment | `GET /v1/payments/{payment_id}` |
| Verify Payment Signature | Utility function (HMAC-SHA256) |
| Webhook Events | `payment.captured`, `payment.failed`, `order.paid`, `refund.created` |
| Webhook Signature | `X-Razorpay-Signature` header verification |

**Webhook Pipeline**:
1. Receive POST at `/api/webhooks/razorpay`
2. Read raw body
3. Verify `X-Razorpay-Signature` using webhook secret
4. Check idempotency via `webhook_events.event_id`
5. Store event with `processing_status = 'pending'`
6. Process: update transaction status, trigger risk/post-payment
7. Mark `processing_status = 'processed'`
8. Notify user via Supabase Realtime

---

## 8. AI/ML Design

### Risk Engine Layers

**Layer 1: Rule Engine** (Deterministic, explainable)
```python
rules = [
    ("new_recipient_high_amount", lambda ctx: ctx.is_new_recipient and ctx.amount > ctx.avg_amount * 3, 30),
    ("rapid_repeated_txns", lambda ctx: ctx.txn_count_last_hour > 5, 25),
    ("unusual_time", lambda ctx: ctx.hour < 6 or ctx.hour > 23, 15),
    ("multiple_failed_attempts", lambda ctx: ctx.failed_count_last_day > 3, 20),
    ("amount_anomaly", lambda ctx: ctx.amount > ctx.p95_amount, 20),
]
```

**Layer 2: Behavioral Baseline**
- Per-user: median amount, typical hours, frequent merchants, txn frequency
- Per-merchant: typical ticket size, peak hours, refund rate
- Deviation scoring: z-score for amount, time, frequency

**Layer 3: ML Anomaly Detection**
- Isolation Forest on features: [amount, hour, day_of_week, merchant_category, txn_count_1h, txn_count_24h, amount_zscore, is_new_recipient]
- Trained on synthetic + historical normal transactions
- Output: anomaly_score (0-1) → scaled to 0-30 points

**Layer 4: Risk Aggregation**
```
risk_score = min(100, rule_score + behavior_score + ml_score + historical_risk)
risk_level = LOW (0-30) | MEDIUM (31-65) | HIGH (66-100)
risk_action = ALLOW | VERIFY | WARN | BLOCK
```

### Gemini Integration
- **Input**: Structured risk decision JSON
- **Prompt**: "Explain this risk decision in {language} for a {citizen/merchant}. Be concise, actionable, non-alarmist."
- **Output**: Natural language explanation + recommendation
- **Fallback**: Template-based explanations if Gemini fails

### Multilingual
- Language stored in `users.language` (en/hi/ta)
- All user-facing text via translation keys
- Gemini prompted with target language

---

## 9. Security Model

| Concern | Implementation |
|---------|----------------|
| Secrets | Server-only via environment variables; never in frontend |
| Razorpay Keys | `RAZORPAY_KEY_ID` (public), `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET` (server only) |
| Gemini API Key | Server only |
| Supabase Keys | `SUPABASE_URL`, `SUPABASE_ANON_KEY` (frontend), `SUPABASE_SERVICE_ROLE_KEY` (backend only) |
| Auth | Supabase Auth (JWT); backend validates via JWKS |
| Authorization | RLS policies + API-level role checks |
| Webhook Security | HMAC-SHA256 signature verification; idempotency via event_id |
| Input Validation | Pydantic schemas on all endpoints |
| Rate Limiting | SlowAPI on auth endpoints, webhook endpoint |
| CORS | Restricted to frontend domain |
| Audit Logging | Structured logs for auth, payments, risk decisions, webhook processing |
| Error Handling | Generic error messages to client; detailed logs server-side |

---

## 10. UI Screen List

### Citizen App
| Screen | Route | Key Components |
|--------|-------|----------------|
| Login/Register | `/auth` | Supabase Auth UI |
| Dashboard | `/` | SpendingSummary, RiskAlerts, RecentTransactions |
| Payment Risk | `/pay/risk` | RiskScoreCard, ReasonList, ActionButtons |
| Transaction History | `/history` | TransactionTable, Filters |
| AI Assistant | `/assistant` | ChatInterface, QuerySuggestions |
| Settings | `/settings` | LanguageSelector, Profile |

### Vendor App
| Screen | Route | Key Components |
|--------|-------|----------------|
| Login/Register | `/auth` | Supabase Auth UI |
| Dashboard | `/` | CollectionSummary, PaymentStatusCards, SuspiciousClaims, RiskAlerts |
| Payment Verification | `/verify` | VerificationForm, ResultCard |
| Transactions | `/transactions` | TransactionTable, Filters, Export |
| Risk Insights | `/insights` | RiskTrendChart, TopRiskSignals |

### Admin/Demo Dashboard
| Screen | Route | Key Components |
|--------|-------|----------------|
| Overview | `/admin` | KPICards, RiskDistributionChart, TransactionVolumeChart |
| Transactions | `/admin/transactions` | AdminTransactionTable |
| Risk Analytics | `/admin/risk` | RiskTrendChart, FraudPatternChart |

---

## 11. Development Phases

| Phase | Deliverables | Est. Effort |
|-------|--------------|-------------|
| **1. Architecture** | This plan, repo structure, env config | 1 day |
| **2. Foundation** | Supabase setup, auth, DB schema, RLS, base FastAPI, base React | 2 days |
| **3. Razorpay** | Order creation, payment flow, webhook endpoint, signature verify, idempotency | 2 days |
| **4. Risk Engine** | Feature extraction, rule engine, behavioral baseline, Isolation Forest, aggregation, policy, unit tests | 3 days |
| **5. AI Layer** | Gemini integration, explanation templates, multilingual, assistant tool-calling | 2 days |
| **6. Citizen UI** | Dashboard, payment risk screen, history, assistant, alerts | 3 days |
| **7. Vendor UI** | Dashboard, verification, transactions, alerts | 2 days |
| **8. Demo Mode** | Synthetic data generator, demo users/merchants, suspicious scenarios | 1 day |
| **9. Testing** | Functional, security, reliability tests | 2 days |
| **Total** | **MVP Ready** | **~18 days** |

---

## 12. Testing Strategy

### Unit Tests (Backend)
- Risk engine: each rule, baseline calculation, isolation forest scoring, aggregation
- Razorpay: signature verification, webhook idempotency, order creation
- Auth: token validation, role extraction
- Schemas: request/response validation

### Integration Tests
- Full payment flow: precheck → order → payment → webhook → transaction record
- Vendor verification: query webhook events → match payment
- RLS: cross-user access denied

### Security Tests
- Webhook: invalid signature rejected, replay attack handled
- Auth: expired token, missing token, role escalation
- Input: SQL injection, XSS payloads in forms
- Secrets: none in frontend bundle

### Reliability Tests
- Duplicate webhook processing
- Gemini timeout → fallback to templates
- ML model failure → rules-only scoring
- Razorpay API timeout → graceful degradation

---

## 13. Deployment Strategy

### Frontend (Vercel)
- Build: `npm run build` → `dist/`
- Env vars: `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_API_BASE_URL`
- Domain: `ai-risk-manager.vercel.app`

### Backend (Render)
- Dockerfile: Python 3.11, install deps, run `uvicorn app.main:app`
- Env vars: All secrets (Razorpay, Gemini, Supabase service role)
- Health check: `GET /health`
- Domain: `ai-risk-manager-api.onrender.com`

### Database (Supabase)
- Run migrations via Supabase CLI or dashboard
- Enable RLS, configure auth providers
- Realtime enabled for notifications

### CI/CD
- GitHub Actions: lint, typecheck, test on PR
- Auto-deploy main branch to Vercel/Render

---

## 14. Known Limitations

| Limitation | Mitigation |
|------------|------------|
| No real fraud labels for supervised ML | Start with Isolation Forest + rules; collect feedback for future training |
| Synthetic demo data only | Clearly label all demo data; don't claim production accuracy |
| Single-region deployment | Acceptable for hackathon; document for future |
| No payment method breakdown (UPI/card/netbanking) | Razorpay webhook includes method; can extend later |
| Limited merchant onboarding | Manual for MVP; add KYC flow later |
| No offline support | Web-only for MVP |
| Gemini rate limits | Cache explanations; fallback templates |
| No regulatory compliance (RBI, PCI-DSS) | Prototype only; document gaps |