-- ==========================================================
-- Migration 005: Verification Challenges & Audit Log Schema
-- ==========================================================

-- 1. Verification Challenges Table
CREATE TABLE IF NOT EXISTS verification_challenges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    challenge_type TEXT NOT NULL DEFAULT 'OTP', -- OTP, RECIPIENT_CONFIRM, COMPLIANCE_REVIEW
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'VERIFIED', 'FAILED', 'EXPIRED')),
    challenge_token TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    expires_at TIMESTAMPTZ NOT NULL,
    verified_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_verification_challenges_txn ON verification_challenges(transaction_id);
CREATE INDEX IF NOT EXISTS idx_verification_challenges_status ON verification_challenges(status);

-- 2. Transaction Audits Table
CREATE TABLE IF NOT EXISTS transaction_audits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    event_name TEXT NOT NULL, -- e.g. PAYMENT_CAPTURED, POST_PAYMENT_PROCESSED, VERIFICATION_SUCCESS, RISK_FLAGGED
    actor TEXT NOT NULL DEFAULT 'SYSTEM',
    details JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_transaction_audits_txn ON transaction_audits(transaction_id);
CREATE INDEX IF NOT EXISTS idx_transaction_audits_created ON transaction_audits(created_at DESC);
