# 🛡️ AI Risk Manager for Bharat

> **AI-powered payment safety platform for India's everyday digital payments**
> Built for UPI-era citizens, street vendors, and micro-merchants.

[![Tests](https://img.shields.io/badge/tests-47%20passed-brightgreen)](backend/tests/)
![TypeScript](https://img.shields.io/badge/TypeScript-zero%20errors-brightgreen)
![Stack](https://img.shields.io/badge/stack-FastAPI%20%7C%20React%20%7C%20Supabase%20%7C%20Razorpay%20%7C%20Gemini-blue)

---

## 🎯 What This Is

A two-sided AI-powered payment risk platform that protects:

1. **Citizens / Payers** — risk scoring before every payment, AI-powered explanations
2. **Micro-merchants / Vendors** — real-time payment verification (never trust a screenshot)

**The core principle:**
> AI analyses real payment events from Razorpay. It never pretends an LLM itself is a fraud detector.

---

## 🏗️ Architecture

```text
Frontend (React/Vite) ──► Backend (FastAPI) ──► Razorpay API
     Port: 3111                Port: 8000           Webhooks
                                   │
              ┌────────────────────┼──────────────────────┐
              │               Risk Engine               │
              │  Rules → Behavioral Baseline → ML (IF)  │
              │         → Aggregator → Score           │
              └────────────────────┬──────────────────────┘
                                   │
                            Gemini AI (1.5-flash)
                         Explanation + Multilingual
                                   │
                              Supabase (DB + Auth + RLS)
```

### Risk Engine Layers (Skill X — Defensive Architecture)

1. **Rule Engine** — deterministic signal detection (new recipient, unusual time, rapid txns, failed attempts, amount anomaly)
2. **Behavioral Baseline** — historical pattern deviation (IQR, velocity, merchant frequency)
3. **ML Anomaly Detection** — Isolation Forest on 8-dimensional feature space
4. **Risk Aggregator** — weighted combination with capped scoring (0–100)

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+ (`C:\Python314\python.exe`)
- Node.js 20+
- Supabase account (for auth + DB)
- Optional: Razorpay test keys, Gemini API key

### 1. Backend Setup

```bash
cd backend
copy .env.example .env
# Edit .env with your real keys

C:\Python314\python.exe -m pip install -r requirements.txt
C:\Python314\python.exe -m uvicorn app.main:app --port 8000 --reload
```

Backend runs at: **`http://localhost:8000`**
API docs at: **`http://localhost:8000/docs`**

### 2. Database Setup

Run the migrations in your Supabase SQL editor:

```sql
-- Run: database/migrations/001_init.sql
-- Then: database/seed/001_demo_data.sql (for demo data)
```

### 3. Frontend Setup

```bash
cd frontend
npm install --legacy-peer-deps
npm run dev
```

Frontend runs at: **`http://localhost:3111`**

---

## 🧪 Running Tests

```bash
cd backend
C:\Python314\python.exe -m pytest tests/ -v
```

**Test results: 47 passed, 2 skipped** (skipped require real Supabase connection)

Test coverage:

- `test_razorpay.py` — HMAC signature verification, webhook parsing
- `test_risk_engine.py` — All rule triggers, aggregator boundaries, Isolation Forest
- `test_schemas.py` — Pydantic schema validation
- `test_webhook_api.py` — FastAPI webhook endpoint integration

---

## 📡 Key API Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/api/risk/precheck` | AI risk score before payment |
| `GET` | `/api/risk/{txn_id}` | Full risk decision |
| `POST` | `/api/ai/explain-risk` | Gemini explanation in EN/HI/TA |
| `POST` | `/api/ai/assistant` | Conversational payment assistant |
| `POST` | `/api/payments/create-order` | Create Razorpay order |
| `POST` | `/api/webhooks/razorpay` | Razorpay webhook (HMAC verified) |
| `GET` | `/api/vendor/dashboard` | Vendor metrics |
| `POST` | `/api/vendor/payment-verification` | Verify payment claim |
| `GET` | `/api/admin/dashboard` | Admin metrics |

---

## 🔐 Security Design

- **JWT auth via Supabase** — JWKS-based RS256 + HS256 fallback
- **Webhook HMAC-SHA256** — signature verified before any processing
- **Idempotent webhooks** — deduplication via `event_id` uniqueness constraint
- **RLS policies** — users only see their own transactions
- **No screenshot trust** — verification is always against Razorpay API records
- **Demo mode** — placeholder keys return mock data, never crash

---

## 🛡️ Demo Mode

With placeholder API keys, the system operates in full demo mode:

- Risk engine runs with synthetic transaction context
- Gemini falls back to multilingual templates (EN/HI/TA)
- Razorpay orders return mock `order_DEMO_` IDs
- All UI flows are fully functional

---

## 🌐 Frontend Pages

| Route | Page | Role |
| --- | --- | --- |
| `/` | Citizen Dashboard | citizen |
| `/pay` | Payment Risk Check | citizen |
| `/history` | Transaction History | citizen |
| `/assistant` | AI Risk Assistant | citizen |
| `/vendor` | Vendor Dashboard | merchant |
| `/vendor/verify` | Payment Verification | merchant |
| `/vendor/transactions` | Vendor Transactions | merchant |
| `/admin` | Admin Analytics | admin |
| `/auth` | Login / Register | all |

---

## 🔑 Environment Variables

### Backend (`.env`)

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_JWT_SECRET=...
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...
RAZORPAY_WEBHOOK_SECRET=...
GEMINI_API_KEY=...
DEMO_MODE=true
CORS_ORIGINS=http://localhost:3111
```

### Frontend (`.env.local`)

```env
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=...
VITE_API_BASE_URL=http://localhost:8000
```

---

## 📐 Design Philosophy

Built with all 6 engineering disciplines:

- **GSD** — Autonomous milestone execution
- **UI UX PRO MAX** — Inter font, glassmorphism, micro-animations, animated SVG gauge
- **RALPH Loop** — Self-healing TypeScript fixes, 47 green tests
- **Skill X** — Multi-layer risk engine, defensive architecture
- **CodeRabbit** — Security audit, HMAC verification, RLS enforcement
- **Claude SEO** — Semantic HTML, WCAG contrast, meta tags

---

*This is a hackathon prototype. All risk scores are illustrative and not a guarantee against fraud.*
