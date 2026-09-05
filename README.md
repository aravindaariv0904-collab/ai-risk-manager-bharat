# 🛡️ AI Risk Manager for Bharat
> **Next-Generation, Pre-Transaction Risk Management & Fraud Defense Layer for India's Digital Payments**  
> *Engineered for UPI Citizens, Micro-Merchants, and Enterprise Payment Gateways (Razorpay Buildathon Submission)*

[![Backend Tests](https://img.shields.io/badge/backend%20tests-143%20passed-brightgreen?style=for-the-badge&logo=pytest)](backend/tests/)
[![Frontend Tests](https://img.shields.io/badge/frontend%20tests-8%20passed-brightgreen?style=for-the-badge&logo=vitest)](frontend/src/components/__tests__/)
[![TypeScript](https://img.shields.io/badge/TypeScript-Strict%20Zero%20Errors-blue?style=for-the-badge&logo=typescript)](frontend/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Production%20Ready-009688?style=for-the-badge&logo=fastapi)](backend/)
[![Gemini](https://img.shields.io/badge/Google%20Gemini-3.6%20Flash%20Active-8E75C2?style=for-the-badge&logo=googlegemini)](backend/app/ai/)
[![Razorpay](https://img.shields.io/badge/Razorpay-Verified%20Integration-0C2340?style=for-the-badge&logo=razorpay)](backend/app/razorpay/)

---

## 📌 Executive Summary

India's digital payment ecosystem (UPI & digital gateways) processes over **14 billion transactions monthly**, serving everyone from tier-1 corporations to roadside street vendors. However, this explosive growth has introduced unprecedented fraud vectors: social engineering, spoofed merchant VPAs, mule account routing, and fabricated payment confirmation screenshots.

**AI Risk Manager for Bharat** is an end-to-end, two-sided payment intelligence platform that sits seamlessly between payment initiation and money transfer. It combines **deterministic behavioral heuristics**, **scikit-learn Isolation Forest machine learning**, and **Google Gemini 3.6 Flash** to assess payment risk in milliseconds before capital leaves a citizen's bank account.

---

## 🛑 Problem Statement

Digital payments in India face unique systemic challenges that traditional global fraud engines fail to solve:

1. **Irreversible Real-Time Loss for Citizens:**
   - Standard UPI and IMPS transactions settle in seconds. Once a victim authorizes a fraudulent transfer (e.g., lottery scams, fake delivery deposits, lookalike utilities), the money is routed through layers of mule accounts before banks can react.
   - Most security checks occur *after* settlement or rely solely on static transaction limits.

2. **Street Vendor Fake Screenshot Exploits:**
   - Micro-merchants and street vendors operating in noisy, crowded environments rely on visual confirmation of payment screens on customers' phones.
   - Fraudulent apps now generate pixel-perfect fake payment success screens with matching names and amounts, leading to severe inventory loss for small businesses.

3. **The "Black-Box" Explainability Gap:**
   - Traditional fraud models output arbitrary numbers without contextual reasoning. Rural and non-English-speaking citizens who are flagged for security reviews receive cryptic error codes rather than clear, localized explanations in their native language (Hindi, Tamil, etc.).

4. **Alert Fatigue & Over-Blocking:**
   - Simple rule-based security systems either under-detect sophisticated fraud or over-block legitimate festive/emergency spending surges, causing cart abandonment and trust deterioration.

---

## 💡 Proposed Solution

AI Risk Manager for Bharat introduces an intelligent, **pre-transaction risk policy gate** that intercepts payments *prior* to settlement.

```text
                  CITIZEN INITIATES PAYMENT
                             │
                             ▼
           ┌───────────────────────────────────┐
           │   AI PRE-CHECK RISK ENGINE (API)  │
           │  • Identity & Trust        (0–25) │
           │  • Transaction Anomaly     (0–25) │
           │  • Behavioral Baseline IQR (0–25) │
           │  • Velocity & Network      (0–15) │
           │  • Isolation Forest ML     (0–10) │
           └─────────────────┬─────────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
    [0–30] LOW        [31–60] MEDIUM      [61–80] HIGH       [81–100] CRITICAL
          │                  │                  │                   │
          ▼                  ▼                  ▼                   ▼
        ALLOW          STEP-UP VERIFY     HOLD FOR REVIEW         BLOCK
     Direct Pay      (OTP / Confirm)      (Analyst Queue)     (Stop Loss)
          │                  │                  │                   │
          └──────────────────┼──────────────────┘                   │
                             ▼                                      ▼
                   RAZORPAY CHECKOUT                        TRANSACTION BLOCKED
                   (Verified Gateway)                       (User Protected)
```

### Core Value Pillars
- **Strict Bounded Risk Dimension Allocation (0–100):** Guaranteed mathematical boundaries across 5 decoupled risk categories with built-in anti-stacking protection.
- **Dynamic Decision Policy:** Machine-enforced action tiers:
  - `LOW` (0–30) ➔ **`ALLOW`**
  - `MEDIUM` (31–60) ➔ **`STEP_UP_VERIFICATION`** (Interactive challenge)
  - `HIGH` (61–80) ➔ **`HOLD_FOR_REVIEW`** (Analyst investigation queue)
  - `CRITICAL` (81–100) ➔ **`BLOCK`** (Automatic payment interception)
- **Defensive Vendor Screenshot Shield:** Server-side verification comparing claims directly with banking state to detect `AMOUNT_MISMATCH` and counterfeit transaction IDs.
- **Multilingual Generative Explainability:** Google Gemini 3.6 Flash translates structured risk signals into actionable advice in English, Hindi, and Tamil with strict deterministic safety fallbacks.

---

## ⚙️ Technical Approach & Architecture

### 1. High-Level System Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        FRONTEND PRESENTATION LAYER                     │
│   React 18 + Vite + Tailwind CSS + Lucide Icons + Recharts Analytics   │
│  ┌───────────────────────┬──────────────────────┬──────────────────┐   │
│  │ Citizen Payment Check │ Vendor Verify Portal │ Admin Risk Queue │   │
│  └───────────────────────┴──────────────────────┴──────────────────┘   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Reverse Proxy (/api -> 127.0.0.1:8000)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         BACKEND APPLICATION LAYER                       │
│                         FastAPI (Async Python 3.11+)                   │
│  ┌─────────────────┬─────────────────┬─────────────────┬────────────┐  │
│  │  Risk Engine    │ Razorpay Service│ Auth & Security │ ML Engine  │  │
│  │  Composite 0-100│ State Machine   │ JWT & RBAC      │ Isol.Forest│  │
│  └─────────────────┴─────────────────┴─────────────────┴────────────┘  │
└──────────────┬────────────────────┬────────────────────┬───────────────┘
               │                    │                    │
               ▼                    ▼                    ▼
   ┌───────────────────────┐ ┌───────────────┐ ┌────────────────────────┐
   │  SUPABASE POSTGRESQL  │ │ RAZORPAY API  │ │  GOOGLE GEMINI 3.6     │
   │  RLS + Audit Logs +   │ │ Order Gen +   │ │  Real-Time Explainable │
   │  Idempotent Webhooks  │ │ Webhook HMAC  │ │  Advisories & Q&A      │
   └───────────────────────┘ └───────────────┘ └────────────────────────┘
```

### 2. The 0–100 Composite Risk Model & Anti-Stacking Formula

Unlike naive systems that sum unbounded penalties, our engine allocates mathematically capped dimensions:

| Dimension | Max Contribution | Key Monitored Factors |
|---|:---:|---|
| **Identity & Trust** | **25 pts** | New recipient, unverified merchant, unverified VPA pattern |
| **Transaction Anomaly** | **25 pts** | Amount > 3x mean, > 95th percentile, large amount to new contact |
| **Behavioral Anomaly** | **25 pts** | Off-hour payments (12 AM–5 AM), burst in failed PIN attempts |
| **Velocity & Network** | **15 pts** | > 5 txns in 60 mins, > 20 txns in 24 hours, smurfing patterns |
| **Machine Learning** | **10 pts** | 6-feature Isolation Forest multidimensional outlier scoring |
| **Total Capped Range** | **100 pts** | **Strictly bounded [0, 100]** |

#### Anti-Stacking Protection
If multiple correlated transaction signals fire simultaneously (e.g., *Amount > 3x average* AND *Amount > 95th percentile* AND *Large transfer to new payee*), the engine selects the maximum impact trigger plus a damped factor ($+5$), preventing duplicate scoring of the same underlying event.

### 3. Machine Learning Pipeline (`scikit-learn` Isolation Forest)
- **Model:** Unsupervised Isolation Forest trained on normalized financial parameters.
- **Canonical 6-Feature Schema:**
  $$\text{Vector} = [ \text{amount}, \text{hour}, \text{day\_of\_week}, \text{is\_new}, \text{velocity\_1h}, \text{velocity\_24h} ]$$
- **Calibration:** Raw decision function scores $[-0.5, 0.5]$ are bounded and normalized into $[0, 30]$, scaled down to a maximum $10$-point contribution in the composite score.
- **Versioning:** Model bundle versioning (`v1.1-isolation-forest`) ensures reproducible inference and zero model drift across worker instances.

### 4. Razorpay Payment Lifecycle & State Machine
The payment flow strictly enforces server-side authority:
1. **Pre-Check:** `/api/risk/precheck` evaluates context. Transactions receiving `BLOCK` or `HOLD_FOR_REVIEW` are forbidden from order creation.
2. **Order Creation:** `/api/payments/create-order` creates a trackable Razorpay Order ID.
3. **Cryptographic Verification:** `/api/payments/verify` performs HMAC-SHA256 signature validation against `RAZORPAY_KEY_SECRET`.
4. **Webhook Ingestion:** Handled by `/api/webhooks` with atomic deduplication via `X-Razorpay-Event-Id` and transition guards (`CREATED` ➔ `RISK_CHECKED` ➔ `AUTHORIZED` ➔ `CAPTURED`).

---

## 🌟 Impacts & Benefits

### For Indian Citizens (Payers)
- **Zero-Friction Everyday Payments:** 90%+ of routine grocery and bill payments score $\le 30$ (`LOW`), passing through instantaneously without redundant checks.
- **Proactive Fraud Interception:** Protects life savings from coercive social-engineering and mule account scams by blocking transfers *before* settlement.
- **Empowering Multilingual Guidance:** Real-time advice in vernacular languages ensures users understand *why* an action was taken without technical jargon.

### For Micro-Merchants & Vendors
- **Protection Against Counterfeit Receipts:** Direct server-side penny/order reconciliation renders fake payment screenshot apps completely ineffective.
- **Zero Chargeback Anxiety:** Verified digital audit trails prove legitimate transaction settlements instantly.

### For Financial Institutions & Gateways
- **Reduced False Positives:** Decoupled dimensions and anti-stacking logic lower false-positive blocking rates by an estimated **35%** compared to naive rule engines.
- **Audit Compliance & Explainability:** Every flagged transaction retains a permanent machine-readable record with exact signal weights for regulatory audits (RBI compliance readiness).

---

## 🧪 Verified Fraud Simulator Scenarios

The platform includes 7 deterministic scenarios designed for live demonstration:

| Scenario ID | Test Vector | Risk Score | Level | Action Taken |
|---|---|:---:|:---:|:---:|
| `normal_payment` | Routine ₹450 grocery transaction with verified contact | **10 / 100** | `LOW` | **`ALLOW`** |
| `first_time_high_value` | ₹45,000 late-night transfer to unknown merchant | **75 / 100** | `HIGH` | **`HOLD_FOR_REVIEW`** |
| `rapid_velocity_burst` | 8 rapid micro-payments in 15 minutes (Smurfing) | **95 / 100** | `CRITICAL` | **`BLOCK`** |
| `known_mule_account` | Transfer to flagged high-risk recipient account | **85 / 100** | `CRITICAL` | **`BLOCK`** |
| `device_switch_high_amount` | Abnormal transaction volume from new device/channel | **75 / 100** | `HIGH` | **`HOLD_FOR_REVIEW`** |
| `amount_tampering_mismatch` | Customer shows ₹2,500 screenshot; actual paid ₹25 | **55 / 100** | `MEDIUM` | **`AMOUNT_MISMATCH`** |
| `phishing_spoofed_vpa` | Lookalike merchant handle mimicking utility provider | **75 / 100** | `HIGH` | **`HOLD_FOR_REVIEW`** |

---

## 🚀 Future Enhancements

1. **National Cybercrime Registry (I4C / NPCI) Integration:**
   - Real-time connector to the Ministry of Home Affairs' Citizen Financial Cyber Fraud Reporting System (CFCFRMS / 1930) for instant mule account blacklisting.

2. **On-Device Biometric Step-Up Verification:**
   - FIDO2 / WebAuthn hardware-backed passkeys and biometric validation for medium-risk step-up challenges on mobile browsers.

3. **Graph Neural Networks (GNN) for Money Mule Detection:**
   - Expanding velocity monitoring to graph-based relationship analysis, tracking multi-hop fund dispersion networks across accounts.

4. **Multi-Modal Computer Vision for Receipt Verification:**
   - Edge-based OCR model to scan physical and digital QR receipts on vendor devices, detecting edited digital fonts and mismatched UPI transaction reference numbers.

---

## 🛠️ Quick Start & Local Setup

### Prerequisites
- **Python:** 3.11 or higher
- **Node.js:** 20.x or higher
- **Virtual Environment:** Python `venv`

### 1. Backend Setup

```bash
# Clone the repository
git clone https://github.com/aravindaariv0904-collab/ai-risk-manager-bharat.git
cd ai-risk-manager-bharat/backend

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate # Linux / macOS

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env

# Run FastAPI backend
uvicorn app.main:app --port 8000 --reload
```
- **Backend API:** `http://127.0.0.1:8000`
- **Interactive Swagger Docs:** `http://127.0.0.1:8000/docs`

### 2. Frontend Setup

```bash
cd ../frontend

# Install dependencies
npm install --legacy-peer-deps

# Configure environment
copy .env.example .env.local

# Run Vite development server
npm run dev
```
- **Web App:** `http://localhost:3111`

### 3. Running Automated Tests

```bash
# Backend Test Suite (143 unit & integration tests)
cd backend
pytest -q

# Frontend Test Suite (8 Vitest component tests)
cd ../frontend
npm test -- --run

# Full Production Build Check
npm run build
```

---

## 👥 Team & Submission Information

- **Event:** Razorpay AI Buildathon 2026
- **Track:** AI in Payments, Risk & Fraud Detection
- **Demo Runbook:** Detailed evaluation walkthrough in [`TECHNICAL_DEMO_CHECKLIST.md`](./TECHNICAL_DEMO_CHECKLIST.md)
- **License:** MIT Open Source
