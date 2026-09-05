-- ============================================
-- AI Risk Manager for Bharat — Database Schema
-- Run in Supabase SQL Editor or via migrations
-- ============================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------- USERS ----------
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_user_id UUID UNIQUE NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    phone TEXT,
    role TEXT NOT NULL DEFAULT 'citizen' CHECK (role IN ('citizen', 'merchant', 'admin')),
    language TEXT NOT NULL DEFAULT 'en' CHECK (language IN ('en', 'hi', 'ta')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_auth_user_id ON users(auth_user_id);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- ---------- MERCHANTS ----------
CREATE TABLE IF NOT EXISTS merchants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    business_name TEXT NOT NULL,
    business_category TEXT,
    phone TEXT,
    upi_id TEXT,
    is_verified BOOLEAN NOT NULL DEFAULT false,
    risk_profile JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_merchants_user_id ON merchants(user_id);
CREATE INDEX IF NOT EXISTS idx_merchants_phone ON merchants(phone);
CREATE INDEX IF NOT EXISTS idx_merchants_upi_id ON merchants(upi_id);

-- ---------- TRANSACTIONS ----------
CREATE TABLE IF NOT EXISTS transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    razorpay_payment_id TEXT UNIQUE,
    razorpay_order_id TEXT,
    payer_id UUID NOT NULL REFERENCES users(id),
    merchant_id UUID NOT NULL REFERENCES merchants(id),
    amount BIGINT NOT NULL CHECK (amount > 0),
    currency TEXT NOT NULL DEFAULT 'INR',
    status TEXT NOT NULL DEFAULT 'created'
        CHECK (status IN ('created', 'pending', 'captured', 'failed', 'refunded')),
    risk_score INTEGER CHECK (risk_score BETWEEN 0 AND 100),
    risk_level TEXT CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    risk_action TEXT CHECK (risk_action IN ('ALLOW', 'VERIFY', 'WARN', 'BLOCK', 'STEP_UP_VERIFICATION', 'HOLD_FOR_REVIEW')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_transactions_payer_id ON transactions(payer_id);
CREATE INDEX IF NOT EXISTS idx_transactions_merchant_id ON transactions(merchant_id);
CREATE INDEX IF NOT EXISTS idx_transactions_payer_created ON transactions(payer_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_merchant_created ON transactions(merchant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_razorpay_order ON transactions(razorpay_order_id);
CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status);
CREATE INDEX IF NOT EXISTS idx_transactions_risk_level ON transactions(risk_level);

-- ---------- RISK EVENTS ----------
CREATE TABLE IF NOT EXISTS risk_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    signal_name TEXT NOT NULL,
    signal_value JSONB DEFAULT '{}'::jsonb,
    severity TEXT NOT NULL CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH')),
    score_impact INTEGER NOT NULL DEFAULT 0,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_risk_events_transaction_id ON risk_events(transaction_id);

-- ---------- RISK DECISIONS ----------
CREATE TABLE IF NOT EXISTS risk_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL UNIQUE REFERENCES transactions(id) ON DELETE CASCADE,
    score INTEGER NOT NULL CHECK (score BETWEEN 0 AND 100),
    level TEXT NOT NULL CHECK (level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    action TEXT NOT NULL CHECK (action IN ('ALLOW', 'VERIFY', 'WARN', 'BLOCK', 'STEP_UP_VERIFICATION', 'HOLD_FOR_REVIEW')),
    explanation TEXT,
    category_scores JSONB DEFAULT '{}'::jsonb,
    explanation_data JSONB DEFAULT '{}'::jsonb,
    model_version TEXT NOT NULL DEFAULT 'v2.0',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_risk_decisions_transaction_id ON risk_decisions(transaction_id);

-- ---------- WEBHOOK EVENTS ----------
CREATE TABLE IF NOT EXISTS webhook_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id TEXT UNIQUE NOT NULL,
    event_type TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    processing_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (processing_status IN ('pending', 'processed', 'failed', 'duplicate')),
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_webhook_events_event_id ON webhook_events(event_id);
CREATE INDEX IF NOT EXISTS idx_webhook_events_status ON webhook_events(processing_status);

-- ---------- FEEDBACK ----------
CREATE TABLE IF NOT EXISTS feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    label TEXT CHECK (label IN ('legitimate', 'suspicious', 'fraud')),
    fraud_confirmed BOOLEAN,
    user_feedback TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_transaction_id ON feedback(transaction_id);

-- ============================================
-- ROW LEVEL SECURITY
-- ============================================

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE merchants ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE risk_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE risk_decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE webhook_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE feedback ENABLE ROW LEVEL SECURITY;

-- Users: see only own profile
DROP POLICY IF EXISTS users_own ON users;
CREATE POLICY users_own ON users
    FOR SELECT USING (auth.uid() = auth_user_id);

DROP POLICY IF EXISTS users_own_insert ON users;
CREATE POLICY users_own_insert ON users
    FOR INSERT WITH CHECK (auth.uid() = auth_user_id);

DROP POLICY IF EXISTS users_own_update ON users;
CREATE POLICY users_own_update ON users
    FOR UPDATE USING (auth.uid() = auth_user_id);

-- Merchants: see own merchant record; merchants readable by all authenticated (for payment)
DROP POLICY IF EXISTS merchants_select ON merchants;
CREATE POLICY merchants_select ON merchants
    FOR SELECT USING (auth.role() = 'authenticated');

DROP POLICY IF EXISTS merchants_own_insert ON merchants;
CREATE POLICY merchants_own_insert ON merchants
    FOR INSERT WITH CHECK (
        user_id IN (SELECT id FROM users WHERE auth_user_id = auth.uid())
    );

DROP POLICY IF EXISTS merchants_own_update ON merchants;
CREATE POLICY merchants_own_update ON merchants
    FOR UPDATE USING (
        user_id IN (SELECT id FROM users WHERE auth_user_id = auth.uid())
    );

-- Transactions: payer sees payments they made; merchant sees payments to their business
DROP POLICY IF EXISTS transactions_payer ON transactions;
CREATE POLICY transactions_payer ON transactions
    FOR SELECT USING (
        payer_id IN (SELECT id FROM users WHERE auth_user_id = auth.uid())
    );

DROP POLICY IF EXISTS transactions_merchant ON transactions;
CREATE POLICY transactions_merchant ON transactions
    FOR SELECT USING (
        merchant_id IN (
            SELECT id FROM merchants WHERE user_id IN (
                SELECT id FROM users WHERE auth_user_id = auth.uid()
            )
        )
    );

DROP POLICY IF EXISTS transactions_payer_insert ON transactions;
CREATE POLICY transactions_payer_insert ON transactions
    FOR INSERT WITH CHECK (
        payer_id IN (SELECT id FROM users WHERE auth_user_id = auth.uid())
    );

-- Risk events / decisions: visible to the payer or merchant of the transaction
DROP POLICY IF EXISTS risk_events_select ON risk_events;
CREATE POLICY risk_events_select ON risk_events
    FOR SELECT USING (
        transaction_id IN (SELECT id FROM transactions WHERE
            payer_id IN (SELECT id FROM users WHERE auth_user_id = auth.uid())
            OR
            merchant_id IN (SELECT id FROM merchants WHERE user_id IN (
                SELECT id FROM users WHERE auth_user_id = auth.uid()
            ))
        )
    );

DROP POLICY IF EXISTS risk_decisions_select ON risk_decisions;
CREATE POLICY risk_decisions_select ON risk_decisions
    FOR SELECT USING (
        transaction_id IN (SELECT id FROM transactions WHERE
            payer_id IN (SELECT id FROM users WHERE auth_user_id = auth.uid())
            OR
            merchant_id IN (SELECT id FROM merchants WHERE user_id IN (
                SELECT id FROM users WHERE auth_user_id = auth.uid()
            ))
        )
    );

-- Feedback: users can create feedback on their own transactions
DROP POLICY IF EXISTS feedback_insert ON feedback;
CREATE POLICY feedback_insert ON feedback
    FOR INSERT WITH CHECK (
        transaction_id IN (SELECT id FROM transactions WHERE
            payer_id IN (SELECT id FROM users WHERE auth_user_id = auth.uid())
        )
    );

DROP POLICY IF EXISTS feedback_select ON feedback;
CREATE POLICY feedback_select ON feedback
    FOR SELECT USING (
        transaction_id IN (SELECT id FROM transactions WHERE
            payer_id IN (SELECT id FROM users WHERE auth_user_id = auth.uid())
        )
    );

-- Webhook events: no public access; admin service-role only
DROP POLICY IF EXISTS webhook_events_admin ON webhook_events;
CREATE POLICY webhook_events_admin ON webhook_events
    FOR ALL USING (false);

-- Admin Global Access Policies
DROP POLICY IF EXISTS admin_users_select ON users;
CREATE POLICY admin_users_select ON users
    FOR SELECT USING (EXISTS (SELECT 1 FROM users u WHERE u.auth_user_id = auth.uid() AND u.role = 'admin'));

DROP POLICY IF EXISTS admin_transactions_select ON transactions;
CREATE POLICY admin_transactions_select ON transactions
    FOR SELECT USING (EXISTS (SELECT 1 FROM users u WHERE u.auth_user_id = auth.uid() AND u.role = 'admin'));

DROP POLICY IF EXISTS admin_merchants_select ON merchants;
CREATE POLICY admin_merchants_select ON merchants
    FOR SELECT USING (EXISTS (SELECT 1 FROM users u WHERE u.auth_user_id = auth.uid() AND u.role = 'admin'));