# 🛡️ AI Risk Manager for Bharat

> **AI-Powered Payment Risk Management & Fraud Defense Layer for India's Digital Payments**  
> *Engineered for UPI citizens, micro-merchants, and Razorpay payment flows.*

[![Tests](https://img.shields.io/badge/backend%20tests-143%20passed-brightgreen)](backend/tests/)
[![Frontend Tests](https://img.shields.io/badge/frontend%20tests-8%20passed-brightgreen)](frontend/src/components/__tests__/)
[![TypeScript](https://img.shields.io/badge/TypeScript-zero%20errors-brightgreen)](frontend/)
[![Stack](https://img.shields.io/badge/stack-FastAPI%20%7C%20React%20%7C%20Supabase%20%7C%20Razorpay%20%7C%20Gemini-blue)](https://github.com/aravindaariv0904-collab/ai-risk-manager-bharat)

---

## 🎯 What This Is

**AI Risk Manager for Bharat** is a production-grade, two-sided payment risk engine and fraud-defense platform designed for India's digital payments ecosystem:

1. **Citizens / Payers** — Real-time pre-check composite risk evaluation (0–100) before money leaves the bank account, with risk-adaptive step-up verification for suspicious payments and multilingual AI explanations (English, Hindi, Tamil).
2. **Micro-Merchants / Street Vendors** — Instant server-side payment verification and fake screenshot protection (`AMOUNT_MISMATCH` detection), protecting merchants against tampered receipts and payment claims.
3. **Risk Analysts / Admins** — Fraud investigation queue, review action audit trails (`APPROVE_RELEASE`, `MARK_FALSE_POSITIVE`, `CONFIRM_FRAUD`, `KEEP_ON_HOLD`), and closed-loop feedback metrics.

> **Core Philosophy**:  
> Machine Learning and deterministic heuristic tripwires compute verifiable, bounded risk scores. Generative AI (Gemini) acts strictly as a **multilingual explainer and translator** — it *never* hallucinates risk scores or decides transaction approvals independently.

---

## 🏗️ Architecture & Payment Flow

```text
               CITIZEN INITIATES PAYMENT
                         │
                         ▼
       ┌───────────────────────────────────────┐
       │   PRE-CHECK COMPOSITE RISK ENGINE     │
       │  • Identity / Trust Signals   (0–25)  │
       │  • Transaction Anomaly        (0–25)  │
       │  • Behavioral Baseline & IQR  (0–25)  │
       │  • Velocity / Network Burst   (0–15)  │
       │  • Isolation Forest ML Anomaly(0–10)  │
       └──────────────────┬────────────────────┘
                          │
       ┌──────────────────┼──────────────────┐
  [0–30] LOW        [31–60] MEDIUM      [61–80] HIGH      [81–100] CRITICAL
      │                   │                   │                   │
      ▼                   ▼                   ▼                   ▼
    ALLOW         STEP-UP VERIFY        HOLD FOR REVIEW         BLOCK
  (Proceed)      (Challenge/OTP)      (Analyst Queue)        (Prevent Loss)
                          │                   │
                          └─────────┬─────────┘
                                    │
                                    ▼
       ┌───────────────────────────────────────┐
       │          RAZORPAY CHECKOUT            │
       └──────────────────┬────────────────────┘
                          │
                          ▼
       ┌───────────────────────────────────────┐
       │     WEBHOOK INGESTION & AUDIT LOG     │
       │  • HMAC-SHA256 Signature Verified     │
       │  • X-Razorpay-Event-Id Idempotency    │
       │  • State Machine: Out-of-Order Safety │
       │  • Post-Payment Volume Aggregation    │
       └───────────────────────────────────────┘
```

---

## 🧩 Status of Features

| Feature | Category | Implementation State |
|---|---|:---:|
| **Canonical ML Feature Extraction & Isolation Forest** | Risk Engine | **REAL / IMPLEMENTED** |
| **0–100 Defensible Composite Risk Scoring** | Risk Engine | **REAL / IMPLEMENTED** |
| **Defensible Decision Policy (`ALLOW`, `STEP_UP`, `HOLD`, `BLOCK`)** | Risk Policy | **REAL / IMPLEMENTED** |
| **Behavioral Baseline Engine (Median, IQR, P95, Velocity)** | Risk Engine | **REAL / IMPLEMENTED** |
| **Razorpay Lifecycle State Machine & Idempotency** | Payments | **REAL / IMPLEMENTED** |
| **Webhook Security & Replay Prevention** | Security | **REAL / IMPLEMENTED** |
| **Vendor Verification & Fake Screenshot Defense** | Vendor Security | **REAL / IMPLEMENTED** |
| **Risk-Adaptive Challenge / Step-Up Verification Lifecycle** | Security | **REAL / IMPLEMENTED** |
| **7-Scenario Deterministic Fraud Simulator** | Demo / Testing | **REAL / IMPLEMENTED (`DEMO`)** |
| **Fraud Investigation Dashboard & Feedback Metrics** | Admin / Governance | **REAL / IMPLEMENTED** |
| **Multilingual Gemini Safety Guardrails & Fallbacks** | AI / Explanations | **REAL / IMPLEMENTED** |
| **Supabase Row Level Security (RLS) & Auth** | Database / Auth | **REAL / IMPLEMENTED** |
| **NPCI / I4C Central Cybercrime Registry Connector** | Registry | **ABSTRACT INTERFACE / FUTURE** |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 20+
- Supabase account (or local demo mode)
- Razorpay API Test Keys (optional for live checkout; demo mock fallback provided)
- Google Gemini API Key (optional; deterministic multilingual fallback provided)

### 1. Backend Setup

```bash
cd backend
copy .env.example .env

# Install dependencies in virtualenv
pip install -r requirements.txt

# Run backend API server
uvicorn app.main:app --port 8000 --reload
```
- API Base URL: `http://localhost:8000`
- Interactive Swagger Docs: `http://localhost:8000/docs`

### 2. Frontend Setup

```bash
cd frontend
copy .env.example .env.local

# Install dependencies
npm install --legacy-peer-deps

# Run frontend development server
npm run dev
```
- Frontend UI: `http://localhost:3111`

---

## 🧪 Automated Testing

Run the full end-to-end test suites:

```bash
# Run Backend Pytest Suite (143 tests)
pytest backend/tests -v

# Run Frontend Vitest Suite (8 tests)
cd frontend
npm test -- --run

# Run Frontend Production Build
npm run build
```

---

## 🛡️ Live Demonstration Runbook

For hackathon judges and evaluators, see the complete step-by-step evaluation guide in:
📄 **[`TECHNICAL_DEMO_CHECKLIST.md`](./TECHNICAL_DEMO_CHECKLIST.md)**

Includes live test commands and scenario walkthroughs for:
1. **7 Deterministic Fraud Scenarios** (`/api/simulator/run/{scenario_id}`)
2. **Vendor Fake Screenshot Tampering Check** (`/api/vendor/payment-verification`)
3. **Risk-Adaptive Step-Up Challenge Flow** (`/api/verification/initiate` + `/api/verification/verify`)
4. **Analyst Investigation & Closed-Loop Precision Tracking** (`/api/admin/feedback-metrics`)
