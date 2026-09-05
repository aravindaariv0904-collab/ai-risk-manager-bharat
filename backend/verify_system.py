import asyncio
import httpx
import psycopg2

print("=" * 60)
print("RUNNING COMPLETE END-TO-END SYSTEM VERIFICATION")
print("=" * 60)

# 1. Test Database Connectivity
print("\n[1/5] Testing Supabase PostgreSQL Database...")
try:
    conn = psycopg2.connect(
        dbname="postgres",
        user="postgres.digktcqwnvkdfyhgkroc",
        password="Aariv@948*##",
        host="aws-0-ap-southeast-1.pooler.supabase.com",
        port=6543,
        connect_timeout=8,
    )
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM users")
    user_cnt = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM merchants")
    merchant_cnt = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM transactions")
    txn_cnt = cur.fetchone()[0]
    print(f"  [OK] Database Connected! Users: {user_cnt}, Merchants: {merchant_cnt}, Transactions: {txn_cnt}")
    conn.close()
except Exception as e:
    print(f"  [FAIL] Database Connection Failed: {e}")

# 2. Test Backend Health & API Endpoints
print("\n[2/5] Testing FastAPI Backend Endpoints...")
with httpx.Client(timeout=10.0) as client:
    # Test Merchants List
    r = client.get("http://127.0.0.1:8000/api/merchants", headers={"Authorization": "Bearer demo.citizen"})
    print(f"  GET /api/merchants -> Status {r.status_code} ({len(r.json()) if r.status_code == 200 else r.text})")

    # Test Mobile Number Lookup
    r = client.get("http://127.0.0.1:8000/api/merchants/lookup?phone=9963170070", headers={"Authorization": "Bearer demo.citizen"})
    print(f"  GET /api/merchants/lookup?phone=9963170070 -> Status {r.status_code}, Name: {r.json().get('business_name') if r.status_code == 200 else 'ERR'}")
    merchant_id = r.json().get("id") if r.status_code == 200 else None

    # Test Risk Precheck
    if merchant_id:
        r = client.post(
            "http://127.0.0.1:8000/api/risk/precheck",
            headers={"Authorization": "Bearer demo.citizen"},
            json={"merchant_id": merchant_id, "amount": 25000, "currency": "INR"}
        )
        print(f"  POST /api/risk/precheck -> Status {r.status_code}, Risk Score: {r.json().get('risk_score') if r.status_code == 200 else 'ERR'}")
        txn_id = r.json().get("transaction_id") if r.status_code == 200 else None

        # Test AI Explanation
        if txn_id:
            r = client.post(
                "http://127.0.0.1:8000/api/ai/explain-risk",
                headers={"Authorization": "Bearer demo.citizen"},
                json={
                    "risk_score": 60,
                    "risk_level": "MEDIUM",
                    "reasons": [{"signal_name": "new_contact_first_time", "reason": "First-time transfer", "severity": "MEDIUM", "score_impact": 10}],
                    "language": "en"
                }
            )
            print(f"  POST /api/ai/explain-risk -> Status {r.status_code}, AI Text: {r.json().get('explanation', '')[:60]}...")

# 3. Test Merchant / Vendor API Endpoints
print("\n[3/5] Testing Merchant / Vendor Endpoints...")
with httpx.Client(timeout=10.0) as client:
    # Test Vendor Dashboard
    r = client.get("http://127.0.0.1:8000/api/vendor/dashboard", headers={"Authorization": "Bearer demo.merchant"})
    print(f"  GET /api/vendor/dashboard -> Status {r.status_code}, Collections: {r.json().get('today_collections', 'N/A') if r.status_code == 200 else r.text}")

    # Test Vendor Verify By Details
    r = client.post(
        "http://127.0.0.1:8000/api/vendor/payment-verification",
        headers={"Authorization": "Bearer demo.merchant"},
        json={"amount": 25000, "customer_phone": "9963170070"}
    )
    print(f"  POST /api/vendor/payment-verification -> Status {r.status_code}, Verified: {r.json().get('verified') if r.status_code == 200 else r.text}")

    # Test Vendor Payments
    r = client.get("http://127.0.0.1:8000/api/vendor/payments", headers={"Authorization": "Bearer demo.merchant"})
    print(f"  GET /api/vendor/payments -> Status {r.status_code}, Count: {len(r.json().get('transactions', [])) if r.status_code == 200 else r.text}")

print("\n" + "=" * 60)
print("ALL SYSTEM CHECKS COMPLETED")
print("=" * 60)
