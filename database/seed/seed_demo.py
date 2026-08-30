"""
Demo data seeder for AI Risk Manager for Bharat.

Creates synthetic demo users, merchants, and transactions.
All data is SYNTHETIC — clearly labelled, not real-world fraud data.

Usage:
    cd backend
    python ../database/seed/seed_demo.py
"""

import os
import sys
import uuid
import random
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

from app.config import settings  # noqa: E402
from app.services.supabase_client import get_supabase_admin  # noqa: E402

DEMO_TAG = "SYNTHETIC_DEMO_DATA"


def create_demo_user(supabase, email, name, phone, role, language):
    """Create a demo auth user + profile row via service role."""
    password = "DemoPass123!"
    resp = supabase.auth.admin.create_user(
        email=email,
        password=password,
        email_confirm=True,
        user_metadata={"name": name, "demo": True},
    )
    user = resp.user
    auth_id = user.id

    existing = supabase.table("users").select("id").eq("auth_user_id", auth_id).execute()
    if existing.data:
        return existing.data[0]["id"]

    profile = supabase.table("users").insert({
        "auth_user_id": auth_id,
        "name": name,
        "phone": phone,
        "role": role,
        "language": language,
    }).execute()
    return profile.data[0]["id"]


def create_merchant(supabase, user_id, name, category, avg, p95):
    existing = supabase.table("merchants").select("id").eq("user_id", user_id).execute()
    if existing.data:
        return existing.data[0]["id"]

    merchant = supabase.table("merchants").insert({
        "user_id": user_id,
        "business_name": name,
        "business_category": category,
        "risk_profile": {"baseline_avg": avg, "baseline_p95": p95, "demo": True},
    }).execute()
    return merchant.data[0]["id"]


def seed_transaction(supabase, payer_id, merchant_id, amount, status, risk, level, action, created_at, payment_id=None):
    payment_id = payment_id or f"pay_demo_{uuid.uuid4().hex[:10]}"
    order_id = f"order_demo_{uuid.uuid4().hex[:10]}"

    txn = supabase.table("transactions").insert({
        "razorpay_payment_id": payment_id,
        "razorpay_order_id": order_id,
        "payer_id": payer_id,
        "merchant_id": merchant_id,
        "amount": amount,
        "currency": "INR",
        "status": status,
        "risk_score": risk,
        "risk_level": level,
        "risk_action": action,
        "created_at": created_at.isoformat(),
    }).execute()

    txn_id = txn.data[0]["id"]

    if risk >= 66:
        events = [
            ("amount_anomaly", "Amount significantly above historical average", "HIGH", 20),
            ("new_recipient_high_amount", "New recipient with unusually high amount", "HIGH", 30),
        ]
    elif risk >= 31:
        events = [
            ("unusual_time", "Transaction at an unusual hour", "MEDIUM", 10),
            ("rapid_repeated_txns", "Multiple transactions in a short period", "MEDIUM", 15),
        ]
    else:
        events = [
            ("baseline_normal", "Transaction within typical range", "LOW", 5),
        ]

    for name, reason, severity, impact in events:
        supabase.table("risk_events").insert({
            "transaction_id": txn_id,
            "signal_name": name,
            "signal_value": {},
            "severity": severity,
            "score_impact": impact,
            "reason": reason,
        }).execute()

    supabase.table("risk_decisions").insert({
        "transaction_id": txn_id,
        "score": risk,
        "level": level,
        "action": action,
        "model_version": "v1.0",
        "explanation": f"[{DEMO_TAG}] Synthetic risk decision.",
    }).execute()

    return txn_id


def run():
    print(f"Seeding {DEMO_TAG} into Supabase...")
    supabase = get_supabase_admin()

    now = datetime.utcnow()

    # Demo citizens
    citizens = [
        ("demo.citizen.priya@example.com", "Priya Sharma", "9812345670", "en"),
        ("demo.citizen.rahul@example.com", "Rahul Verma", "9823456781", "hi"),
        ("demo.citizen.karthik@example.com", "Karthik Raja", "9834567892", "ta"),
        ("demo.citizen.anita@example.com", "Anita Devi", "9845678903", "en"),
    ]
    citizen_ids = {}
    for email, name, phone, lang in citizens:
        uid = create_demo_user(supabase, email, name, phone, "citizen", lang)
        citizen_ids[name] = uid
        print(f"  citizen: {name} ({email})")

    # Demo merchants
    merchant_defs = [
        ("Ramesh General Store", "grocery", 350, 1200),
        ("Suresh Tea Stall", "food", 40, 150),
        ("Lakshmi Flower Shop", "retail", 200, 600),
        ("Mohammed Biryani", "restaurant", 250, 700),
        ("Geeta Tailoring", "services", 500, 1500),
    ]
    merchant_ids = {}
    for name, category, avg, p95 in merchant_defs:
        slug = name.lower().split()[0]
        email = f"demo.vendor.{slug}@example.com"
        uid = create_demo_user(supabase, email, name, "98" + str(random.randint(60000000, 99999999)), "merchant", "en")
        mid = create_merchant(supabase, uid, name, category, avg, p95)
        merchant_ids[name] = mid
        print(f"  merchant: {name}")

    # Normal transactions
    print("  Seeding normal (LOW risk) transactions...")
    c = list(citizen_ids.values())
    m = list(merchant_ids.values())
    normal_amounts = [8000, 12000, 25000, 35000, 50000]
    for i in range(20):
        payer = random.choice(c)
        merchant = random.choice(m)
        amount = random.choice(normal_amounts)
        created = now - timedelta(days=random.randint(0, 14), hours=random.randint(6, 18))
        seed_transaction(
            supabase, payer, merchant, amount, "captured",
            random.randint(5, 20), "LOW", "ALLOW", created,
        )

    # High risk transactions (suspicious synthetic scenarios)
    print("  Seeding HIGH risk transactions...")
    high_defs = [
        (citizen_ids["Priya Sharma"], merchant_ids["Mohammed Biryani"], 850000, "pending", 84),
        (citizen_ids["Rahul Verma"], merchant_ids["Ramesh General Store"], 1200000, "pending", 90),
        (citizen_ids["Karthik Raja"], merchant_ids["Geeta Tailoring"], 950000, "failed", 82),
        (citizen_ids["Anita Devi"], merchant_ids["Mohammed Biryani"], 450000, "captured", 72),
    ]
    for payer, merchant, amount, status, risk in high_defs:
        seed_transaction(
            supabase, payer, merchant, amount, status, risk, "HIGH", "WARN",
            now - timedelta(minutes=random.randint(5, 30)),
        )

    # Fake payment claim scenario (failed payment claimed as paid)
    print("  Seeding fake-payment-claim scenario...")
    seed_transaction(
        supabase,
        citizen_ids["Anita Devi"],
        merchant_ids["Ramesh General Store"],
        850000,
        "failed",
        70,
        "HIGH",
        "WARN",
        now - timedelta(minutes=3),
        payment_id="pay_demo_fake_claim_001",
    )

    # Rapid repeated transaction pattern
    print("  Seeding rapid repeated transaction pattern...")
    for i in range(5):
        seed_transaction(
            supabase,
            citizen_ids["Rahul Verma"],
            merchant_ids["Suresh Tea Stall"],
            random.choice([30000, 35000, 40000, 45000, 50000]),
            "captured",
            55,
            "MEDIUM",
            "VERIFY",
            now - timedelta(minutes=8 - i),
        )

    print("\nDemo seed complete.")
    print(f"Demo users login: password = DemoPass123!")
    print("NOTE: All data is synthetic and demo-only. It does not represent real fraud patterns.")


if __name__ == "__main__":
    run()