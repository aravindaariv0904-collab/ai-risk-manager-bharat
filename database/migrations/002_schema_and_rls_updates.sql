-- Migration 002: Add first-class merchant lookup fields and Admin RLS Policies

ALTER TABLE merchants ADD COLUMN IF NOT EXISTS phone TEXT;
ALTER TABLE merchants ADD COLUMN IF NOT EXISTS upi_id TEXT;
ALTER TABLE merchants ADD COLUMN IF NOT EXISTS is_verified BOOLEAN NOT NULL DEFAULT false;

CREATE INDEX IF NOT EXISTS idx_merchants_phone ON merchants(phone);
CREATE INDEX IF NOT EXISTS idx_merchants_upi_id ON merchants(upi_id);

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
