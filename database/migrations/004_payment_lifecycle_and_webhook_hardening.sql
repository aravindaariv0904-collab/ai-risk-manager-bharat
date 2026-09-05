-- ==========================================================
-- Migration 004: Payment Lifecycle & Webhook Hardening
-- ==========================================================

-- 1. Expand transactions status check constraint to include all explicit states (upper and lower case compatible)
ALTER TABLE transactions DROP CONSTRAINT IF EXISTS transactions_status_check;
ALTER TABLE transactions ADD CONSTRAINT transactions_status_check 
    CHECK (status IN (
        'CREATED', 'RISK_CHECKED', 'VERIFICATION_REQUIRED', 
        'AUTHORIZED', 'CAPTURED', 'FAILED', 'HELD', 
        'BLOCKED', 'REFUNDED', 'UNKNOWN',
        -- lowercase backward-compatibility
        'created', 'pending', 'captured', 'failed', 'refunded'
    ));

-- 2. Add payment_id, order_id, and processing_error to webhook_events
ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS payment_id TEXT;
ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS order_id TEXT;
ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS processing_error TEXT;

-- 3. Ensure unique index on event_id for atomic idempotency
CREATE UNIQUE INDEX IF NOT EXISTS idx_webhook_events_event_id_unique ON webhook_events(event_id);
CREATE INDEX IF NOT EXISTS idx_webhook_events_payment_id ON webhook_events(payment_id);
CREATE INDEX IF NOT EXISTS idx_webhook_events_order_id ON webhook_events(order_id);
