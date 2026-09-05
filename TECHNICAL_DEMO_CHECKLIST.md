# AI Risk Manager for Bharat — Technical Demo & Verification Checklist

> **Razorpay Buildathon 2026 / Hackathon Production Runbook**  
> *Deterministic ML-Powered Payment Risk Engine, Risk-Adaptive Verification, Webhook Idempotency, and Fraud Defense for Bharat's Digital Payments.*

---

## 1. Executive Summary & Architecture

**AI Risk Manager for Bharat** is an intelligent payment safety layer engineered for Indian digital payments (UPI & Razorpay). It combines deterministic composite risk scoring, behavioral baselining, machine learning anomaly detection (Isolation Forest), risk-adaptive step-up verification, and vendor payment verification against screenshot/receipt tampering.

```
                    ┌─────────────────────────────────────────────────────────┐
                    │               PAYMENT INITIATION (CITIZEN)              │
                    └────────────────────────────┬────────────────────────────┘
                                                 │
                                                 ▼
                    ┌─────────────────────────────────────────────────────────┐
                    │      PRE-CHECK COMPOSITE RISK ENGINE (0 - 100 SCORE)    │
                    │   • Identity & Trust Signals (0 - 25)                   │
                    │   • Transaction Anomaly (0 - 25)                        │
                    │   • Behavioral Baseline & IQR Bounds (0 - 25)           │
                    │   • Velocity & Network Burst (0 - 15)                   │
                    │   • Isolation Forest ML Anomaly (0 - 10)                │
                    └──────┬───────────────┬────────────────┬─────────────────┘
                           │               │                │                 │
              [0 - 30]     │   [31 - 60]   │   [61 - 80]    │   [81 - 100]    │
              LOW          │   MEDIUM      │   HIGH         │   CRITICAL      │
                           ▼               ▼                ▼                 ▼
                     ┌───────────┐  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐
                     │   ALLOW   │  │   STEP-UP   │  │   HOLD FOR   │  │    BLOCK     │
                     │  PAYMENT  │  │VERIFICATION │  │    REVIEW    │  │ TRANSACTION  │
                     └─────┬─────┘  └──────┬──────┘  └──────┬───────┘  └──────────────┘
                           │               │                │
                           ▼               ▼                ▼
                    ┌─────────────────────────────────────────────────────────┐
                    │               RAZORPAY CHECKOUT & GATEWAY               │
                    └────────────────────────────┬────────────────────────────┘
                                                 │
                                                 ▼
                    ┌─────────────────────────────────────────────────────────┐
                    │       IDEMPOTENT WEBHOOK INGESTION & STATE MACHINE       │
                    │   • X-Razorpay-Event-Id & Signature Verification        │
                    │   • Out-of-Order Downgrade Prevention                   │
                    │   • Post-Payment Volume & Velocity Aggregation          │
                    │   • Vendor Verification & Tamper / Mismatch Shield      │
                    └─────────────────────────────────────────────────────────┘
```

---

## 2. 20-Prompt Implementation & Verification Matrix

| Prompt | Component & Focus Area | Implementation Files | Status |
|---|---|---|:---:|
| **1** | Full Architectural Audit & Baseline Verification | `backend/app/main.py`, `database/migrations/` | Verified |
| **2** | Canonical ML Feature Extraction Pipeline & Dimension Checks | `backend/app/risk/ml_pipeline.py`, `backend/tests/test_ml_pipeline.py` | Verified |
| **3** | Composite 0–100 Defensible Risk Scoring Engine | `backend/app/risk/engine.py`, `backend/tests/test_composite_risk.py` | Verified |
| **4** | Defensible Payment Decision Policy & Threshold Config | `backend/app/config.py`, `backend/tests/test_decision_policy.py` | Verified |
| **5** | Explainable Risk Result UI & Signal Score Tags | `frontend/src/components/RiskResultCard.tsx`, `frontend/src/components/__tests__/RiskResultCard.test.tsx` | Verified |
| **6** | Razorpay Lifecycle State Machine & Out-of-Order Safety | `backend/app/payments/state_machine.py`, `backend/tests/test_payments_lifecycle.py` | Verified |
| **7** | Webhook Security, Signature Verification & Idempotency | `backend/app/webhooks/service.py`, `backend/tests/test_webhook_api.py` | Verified |
| **8** | Post-Payment Processing & Audit Logging Pipeline | `backend/app/payments/post_payment.py`, `backend/tests/test_post_payment.py` | Verified |
| **9** | External Registry Interface & Truthful NPCI/I4C Disclosure | `backend/app/services/external_registries.py`, `backend/app/services/npci_directory.py` | Verified |
| **10** | Robust Behavioral Baselining (Median, IQR, P95) | `backend/app/risk/behavioral.py`, `backend/tests/test_behavioral.py` | Verified |
| **11** | Risk-Adaptive Verification Lifecycle & Bypass Protection | `backend/app/payments/verification.py`, `backend/app/api/verification.py` | Verified |
| **12** | Vendor Payment Verification & Fake Screenshot Defense | `backend/app/api/vendor.py`, `backend/tests/test_vendor_verification.py` | Verified |
| **13** | 7-Scenario Deterministic Fraud Simulator (`DEMO`) | `backend/app/api/simulator.py`, `backend/tests/test_simulator.py` | Verified |
| **14** | Fraud Investigation Queue & Human Review Actions | `backend/app/api/admin.py`, `backend/tests/test_investigation.py` | Verified |
| **15** | False Positive Feedback Loop & Precision Metrics | `backend/app/api/admin.py`, `backend/tests/test_investigation.py` | Verified |
| **16** | Safe Gemini Multilingual Guardrails (`en`, `hi`, `ta`) | `backend/app/ai/service.py`, `backend/tests/test_ai_service.py` | Verified |
| **17** | Supabase RLS Policies & Security Hardening | `database/migrations/001-005.sql` | Verified |
| **18** | End-to-End Automated Test Suite (143 Backend + 8 Frontend) | `backend/tests/`, `frontend/src/components/__tests__/` | Verified |
| **19** | Hackathon Dashboard Metrics & Live Aggregations | `backend/app/api/admin.py`, `frontend/src/pages/AdminDashboardPage.tsx` | Verified |
| **20** | Technical Demo Checklist & Live Runbook | `TECHNICAL_DEMO_CHECKLIST.md` | Verified |

---

## 3. Step-by-Step Live Demo Runbook

### Step 1: Automated Verification Check
Run backend and frontend test suites to demonstrate 100% green status across all subsystems:
```powershell
# Backend Test Suite (143 tests passing)
& ".venv\Scripts\python.exe" -m pytest backend/tests -v

# Frontend Vitest Suite (8 tests passing)
cd frontend
npm test -- --run
```

---

### Step 2: Live Demo — Fraud Scenario Simulator
Test the 7 deterministic real-world fraud scenarios:
- **Endpoint**: `GET /api/simulator/scenarios` and `POST /api/simulator/run/{scenario_id}`
1. `normal_payment`: Grocery ₹450 -> `LOW` (0-30) -> Decision: `ALLOW`
2. `first_time_high_value`: ₹85,000 at 2:30 AM -> `HIGH` (61-80) -> Decision: `HOLD_FOR_REVIEW`
3. `rapid_velocity_burst`: 6 rapid transactions in 3 min -> `CRITICAL` -> Decision: `BLOCK`
4. `known_mule_account`: Beneficiary flagged in mule list -> `CRITICAL` -> Decision: `BLOCK`
5. `device_switch_high_amount`: Unrecognized hardware ID + high transfer -> `CRITICAL` -> Decision: `BLOCK`
6. `amount_tampering_mismatch`: Claimed ₹5,000 vs actual ₹50 receipt -> `AMOUNT_MISMATCH` -> Decision: `BLOCK`
7. `phishing_spoofed_vpa`: Spoofed lookalike utility handle -> `HIGH` -> Decision: `HOLD_FOR_REVIEW`

---

### Step 3: Live Demo — Vendor Payment Verification & Fake Screenshot Defense
- Test payment verification with claimed amount:
  - Query: `POST /api/vendor/payment-verification` with `payment_id="pay_sample"` and `amount=500000` (claimed ₹5,000).
  - Actual transaction in Razorpay is ₹50 (`5000` paise).
  - Output: `verified: false`, `verification_status: "AMOUNT_MISMATCH"`, `amount_mismatch: true`.
  - Result: Prevents merchant from falling victim to tampered payment screenshots.

---

### Step 4: Live Demo — Risk-Adaptive Step-Up Verification
1. User attempts ₹6,000 transaction with medium risk (`MEDIUM` -> `STEP_UP_VERIFICATION`).
2. Order creation is gated: payment cannot proceed directly until challenge is answered.
3. System issues verification challenge: `POST /api/verification/initiate` -> returns challenge token with 3 max attempts.
4. User submits OTP: `POST /api/verification/verify` -> upon success, transaction status transitions to `VERIFIED` and Razorpay order is unlocked.
5. 3 failed attempts or expiration immediately transition transaction to `FAILED` / `BLOCKED`.

---

### Step 5: Live Demo — Fraud Investigation & Feedback Metrics
1. Analyst inspects flagged queue: `GET /api/admin/investigations/queue`.
2. Analyst investigates held transaction: `POST /api/admin/transactions/{id}/investigate` with:
   - `APPROVE_RELEASE` (releases payment to `captured`)
   - `MARK_FALSE_POSITIVE` (records legitimate feedback, computes model precision)
   - `CONFIRM_FRAUD` (blocks transaction and records confirmed fraud data point)
3. View feedback metrics: `GET /api/admin/feedback-metrics` returning live `false_positive_rate`, `confirmed_fraud_rate`, and `review_rate`.

---

## 4. Truthful Technical Disclosures

1. **Government & Central Registry Connectors (`external_registries.py`)**:
   - Explicitly documented as `FUTURE INTEGRATION / ABSTRACT INTERFACE`.
   - Real system includes functional fallback logic and never fakes external HTTP calls to I4C / NPCI.
2. **Gemini Generative AI (`ai/service.py`)**:
   - Gemini operates strictly as an **explainer and translator** in English, Hindi, and Tamil.
   - Gemini **never** calculates or alters risk scores or policy decisions (handled 100% deterministically by the Risk Engine).
   - Robust offline fallbacks ensure zero downtime even if Gemini API keys are absent or network is degraded.

---

## 5. Summary of Test Results

- **Backend Pytest Suite**: 143 passed, 0 failed (100% pass rate).
- **Frontend Vitest Suite**: 8 passed, 0 failed (100% pass rate).
- **Frontend Production Build**: Clean build with Vite & TypeScript (`tsc -b && vite build`).
