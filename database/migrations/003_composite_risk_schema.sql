-- ============================================
-- Migration 003: Composite Risk Schema Updates
-- ============================================

-- 1. Update transactions risk_level check constraint to include CRITICAL
ALTER TABLE transactions DROP CONSTRAINT IF EXISTS transactions_risk_level_check;
ALTER TABLE transactions ADD CONSTRAINT transactions_risk_level_check 
    CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'));

-- 2. Update transactions risk_action check constraint to include STEP_UP_VERIFICATION, HOLD_FOR_REVIEW
ALTER TABLE transactions DROP CONSTRAINT IF EXISTS transactions_risk_action_check;
ALTER TABLE transactions ADD CONSTRAINT transactions_risk_action_check 
    CHECK (risk_action IN ('ALLOW', 'VERIFY', 'WARN', 'BLOCK', 'STEP_UP_VERIFICATION', 'HOLD_FOR_REVIEW'));

-- 3. Update risk_decisions level check constraint to include CRITICAL
ALTER TABLE risk_decisions DROP CONSTRAINT IF EXISTS risk_decisions_level_check;
ALTER TABLE risk_decisions ADD CONSTRAINT risk_decisions_level_check 
    CHECK (level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'));

-- 4. Update risk_decisions action check constraint to include STEP_UP_VERIFICATION, HOLD_FOR_REVIEW
ALTER TABLE risk_decisions DROP CONSTRAINT IF EXISTS risk_decisions_action_check;
ALTER TABLE risk_decisions ADD CONSTRAINT risk_decisions_action_check 
    CHECK (action IN ('ALLOW', 'VERIFY', 'WARN', 'BLOCK', 'STEP_UP_VERIFICATION', 'HOLD_FOR_REVIEW'));

-- 5. Add category_scores and explanation_data to risk_decisions
ALTER TABLE risk_decisions ADD COLUMN IF NOT EXISTS category_scores JSONB DEFAULT '{}'::jsonb;
ALTER TABLE risk_decisions ADD COLUMN IF NOT EXISTS explanation_data JSONB DEFAULT '{}'::jsonb;
