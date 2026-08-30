-- ============================================
-- AI Risk Manager — Seed Demo Data
-- Creates demo users, merchants, and synthetic transactions
-- NOTE: All data here is SYNTHETIC demo data for the hackathon.
-- It does NOT represent real-world fraud patterns or accuracy.
-- ============================================

-- Demo users are created against known demo auth users.
-- Adjust auth_user_id values to match your Supabase demo accounts.
-- For a no-auth local demo, values below use fixed UUIDs.

-- ---------- DEMO USERS ----------
INSERT INTO users (id, auth_user_id, name, phone, role, language) VALUES
    ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000a1', 'Priya Sharma', '9812345670', 'citizen', 'en'),
    ('00000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-0000000000a2', 'Rahul Verma', '9823456781', 'citizen', 'hi'),
    ('00000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-0000000000a3', 'Karthik Raja', '9834567892', 'citizen', 'ta'),
    ('00000000-0000-0000-0000-000000000004', '00000000-0000-0000-0000-0000000000a4', 'Anita Devi', '9845678903', 'citizen', 'en'),
    ('00000000-0000-0000-0000-000000000005', '00000000-0000-0000-0000-0000000000a5', 'Meena Kumari', '9856789014', 'citizen', 'ta'),
    ('00000000-0000-0000-0000-000000000010', '00000000-0000-0000-0000-0000000000b0', 'Ramesh General Store', '9867890125', 'merchant', 'en'),
    ('00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-0000000000b1', 'Suresh Tea Stall', '9878901236', 'merchant', 'hi'),
    ('00000000-0000-0000-0000-000000000012', '00000000-0000-0000-0000-0000000000b2', 'Lakshmi Flower Shop', '9889012347', 'merchant', 'ta'),
    ('00000000-0000-0000-0000-000000000013', '00000000-0000-0000-0000-0000000000b3', 'Mohammed Biryani', '9890123458', 'merchant', 'hi'),
    ('00000000-0000-0000-0000-000000000014', '00000000-0000-0000-0000-0000000000b4', 'Geeta Tailoring', '9901234569', 'merchant', 'en'),
    ('00000000-0000-0000-0000-000000000015', '00000000-0000-0000-0000-0000000000b5', 'Demo Admin', '9912345670', 'admin', 'en')
ON CONFLICT (id) DO NOTHING;

-- ---------- DEMO MERCHANTS ----------
INSERT INTO merchants (id, user_id, business_name, business_category, risk_profile) VALUES
    ('10000000-0000-0000-0000-000000000010', '00000000-0000-0000-0000-000000000010', 'Ramesh General Store', 'grocery', '{"baseline_avg": 350, "baseline_p95": 1200}'),
    ('10000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000011', 'Suresh Tea Stall', 'food', '{"baseline_avg": 40, "baseline_p95": 150}'),
    ('10000000-0000-0000-0000-000000000012', '00000000-0000-0000-0000-000000000012', 'Lakshmi Flower Shop', 'retail', '{"baseline_avg": 200, "baseline_p95": 600}'),
    ('10000000-0000-0000-0000-000000000013', '00000000-0000-0000-0000-000000000013', 'Mohammed Biryani', 'restaurant', '{"baseline_avg": 250, "baseline_p95": 700}'),
    ('10000000-0000-0000-0000-000000000014', '00000000-0000-0000-0000-000000000014', 'Geeta Tailoring', 'services', '{"baseline_avg": 500, "baseline_p95": 1500}')
ON CONFLICT (id) DO NOTHING;

-- ---------- SYNTHETIC TRANSACTIONS ----------
-- Normal transactions (typical everyday amounts)
INSERT INTO transactions (id, razorpay_payment_id, razorpay_order_id, payer_id, merchant_id, amount, currency, status, risk_score, risk_level, risk_action, created_at) VALUES
    ('20000000-0000-0000-0000-000000000001', 'pay_demo_normal_0001', 'order_demo_0001', '00000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000011', 8000, 'INR', 'captured', 8, 'LOW', 'ALLOW', NOW() - INTERVAL '2 days'),
    ('20000000-0000-0000-0000-000000000002', 'pay_demo_normal_0002', 'order_demo_0002', '00000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000010', 12000, 'INR', 'captured', 10, 'LOW', 'ALLOW', NOW() - INTERVAL '1 day'),
    ('20000000-0000-0000-0000-000000000003', 'pay_demo_normal_0003', 'order_demo_0003', '00000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000013', 25000, 'INR', 'captured', 12, 'LOW', 'ALLOW', NOW() - INTERVAL '3 hours'),
    ('20000000-0000-0000-0000-000000000004', 'pay_demo_normal_0004', 'order_demo_0004', '00000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000012', 35000, 'INR', 'captured', 15, 'LOW', 'ALLOW', NOW() - INTERVAL '1 hour'),
    ('20000000-0000-0000-0000-000000000005', 'pay_demo_normal_0005', 'order_demo_0005', '00000000-0000-0000-0000-000000000004', '10000000-0000-0000-0000-000000000014', 50000, 'INR', 'captured', 18, 'LOW', 'ALLOW', NOW() - INTERVAL '30 minutes')
ON CONFLICT (razorpay_payment_id) DO NOTHING;

-- Suspicious transactions (high risk synthetic scenarios)
INSERT INTO transactions (id, razorpay_payment_id, razorpay_order_id, payer_id, merchant_id, amount, currency, status, risk_score, risk_level, risk_action, created_at) VALUES
    ('20000000-0000-0000-0000-000000000101', 'pay_demo_high_0001', 'order_demo_0101', '00000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000013', 850000, 'INR', 'pending', 84, 'HIGH', 'WARN', NOW() - INTERVAL '25 minutes'),
    ('20000000-0000-0000-0000-000000000102', 'pay_demo_high_0002', 'order_demo_0102', '00000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000010', 1200000, 'INR', 'pending', 90, 'HIGH', 'WARN', NOW() - INTERVAL '20 minutes'),
    ('20000000-0000-0000-0000-000000000103', 'pay_demo_high_0003', 'order_demo_0103', '00000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000014', 950000, 'INR', 'failed', 82, 'HIGH', 'WARN', NOW() - INTERVAL '15 minutes'),
    ('20000000-0000-0000-0000-000000000104', 'pay_demo_high_0004', 'order_demo_0104', '00000000-0000-0000-0000-000000000004', '10000000-0000-0000-0000-000000000013', 450000, 'INR', 'captured', 72, 'HIGH', 'WARN', NOW() - INTERVAL '10 minutes'),
    ('20000000-0000-0000-0000-000000000105', 'pay_demo_claim_fake', 'order_demo_0105', '00000000-0000-0000-0000-000000000005', '10000000-0000-0000-0000-000000000010', 850000, 'INR', 'failed', 70, 'HIGH', 'WARN', NOW() - INTERVAL '5 minutes')
ON CONFLICT (razorpay_payment_id) DO NOTHING;

-- Rapid repeated suspicious pattern (same payer to same merchant, very fast)
INSERT INTO transactions (id, razorpay_payment_id, razorpay_order_id, payer_id, merchant_id, amount, currency, status, risk_score, risk_level, risk_action, created_at) VALUES
    ('20000000-0000-0000-0000-000000000201', 'pay_demo_rapid_0001', 'order_demo_0201', '00000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000011', 30000, 'INR', 'captured', 55, 'MEDIUM', 'VERIFY', NOW() - INTERVAL '8 minutes'),
    ('20000000-0000-0000-0000-000000000202', 'pay_demo_rapid_0002', 'order_demo_0202', '00000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000011', 40000, 'INR', 'captured', 55, 'MEDIUM', 'VERIFY', NOW() - INTERVAL '7 minutes'),
    ('20000000-0000-0000-0000-000000000203', 'pay_demo_rapid_0003', 'order_demo_0203', '00000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000011', 35000, 'INR', 'captured', 55, 'MEDIUM', 'VERIFY', NOW() - INTERVAL '6 minutes'),
    ('20000000-0000-0000-0000-000000000204', 'pay_demo_rapid_0004', 'order_demo_0204', '00000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000011', 50000, 'INR', 'captured', 55, 'MEDIUM', 'VERIFY', NOW() - INTERVAL '5 minutes'),
    ('20000000-0000-0000-0000-000000000205', 'pay_demo_rapid_0005', 'order_demo_0205', '00000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000011', 45000, 'INR', 'captured', 55, 'MEDIUM', 'VERIFY', NOW() - INTERVAL '4 minutes')
ON CONFLICT (razorpay_payment_id) DO NOTHING;

-- ---------- RISK DECISIONS FOR SEED TRANSACTIONS ----------
INSERT INTO risk_decisions (transaction_id, score, level, action, model_version, created_at) VALUES
    ('20000000-0000-0000-0000-000000000001', 8, 'LOW', 'ALLOW', 'v1.0', NOW() - INTERVAL '2 days'),
    ('20000000-0000-0000-0000-000000000002', 10, 'LOW', 'ALLOW', 'v1.0', NOW() - INTERVAL '1 day'),
    ('20000000-0000-0000-0000-000000000003', 12, 'LOW', 'ALLOW', 'v1.0', NOW() - INTERVAL '3 hours'),
    ('20000000-0000-0000-0000-000000000004', 15, 'LOW', 'ALLOW', 'v1.0', NOW() - INTERVAL '1 hour'),
    ('20000000-0000-0000-0000-000000000005', 18, 'LOW', 'ALLOW', 'v1.0', NOW() - INTERVAL '30 minutes'),
    ('20000000-0000-0000-0000-000000000101', 84, 'HIGH', 'WARN', 'v1.0', NOW() - INTERVAL '25 minutes'),
    ('20000000-0000-0000-0000-000000000102', 90, 'HIGH', 'WARN', 'v1.0', NOW() - INTERVAL '20 minutes'),
    ('20000000-0000-0000-0000-000000000103', 82, 'HIGH', 'WARN', 'v1.0', NOW() - INTERVAL '15 minutes'),
    ('20000000-0000-0000-0000-000000000104', 72, 'HIGH', 'WARN', 'v1.0', NOW() - INTERVAL '10 minutes'),
    ('20000000-0000-0000-0000-000000000105', 70, 'HIGH', 'WARN', 'v1.0', NOW() - INTERVAL '5 minutes'),
    ('20000000-0000-0000-0000-000000000201', 55, 'MEDIUM', 'VERIFY', 'v1.0', NOW() - INTERVAL '8 minutes'),
    ('20000000-0000-0000-0000-000000000202', 55, 'MEDIUM', 'VERIFY', 'v1.0', NOW() - INTERVAL '7 minutes'),
    ('20000000-0000-0000-0000-000000000203', 55, 'MEDIUM', 'VERIFY', 'v1.0', NOW() - INTERVAL '6 minutes'),
    ('20000000-0000-0000-0000-000000000204', 55, 'MEDIUM', 'VERIFY', 'v1.0', NOW() - INTERVAL '5 minutes'),
    ('20000000-0000-0000-0000-000000000205', 55, 'MEDIUM', 'VERIFY', 'v1.0', NOW() - INTERVAL '4 minutes')
ON CONFLICT (transaction_id) DO NOTHING;