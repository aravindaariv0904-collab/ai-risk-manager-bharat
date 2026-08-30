from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from typing import List, Optional
from datetime import datetime, timedelta

from app.schemas import (
    VendorDashboardResponse, SuspiciousClaim, RiskAlert,
    PaymentVerificationRequest, PaymentVerificationResponse,
    TransactionListResponse, TransactionResponse,
)
from app.security.auth import get_current_user_id, get_current_user_role
from app.services.supabase_client import get_supabase_admin
from app.razorpay.service import razorpay_service

router = APIRouter(prefix="/api/vendor", tags=["vendor"])


async def get_merchant_id(user_id: str) -> str:
    supabase = get_supabase_admin()
    user_resp = supabase.table("users").select("id").eq("auth_user_id", user_id).single().execute()
    if not user_resp.data:
        raise HTTPException(status_code=404, detail="User profile not found")

    merchant_resp = supabase.table("merchants").select("id").eq("user_id", user_resp.data["id"]).single().execute()
    if not merchant_resp.data:
        raise HTTPException(status_code=404, detail="Merchant profile not found")
    return merchant_resp.data["id"]


@router.get("/dashboard", response_model=VendorDashboardResponse)
async def vendor_dashboard(user_id: str = Depends(get_current_user_id)):
    supabase = get_supabase_admin()
    merchant_id = await get_merchant_id(user_id)

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

    txns_today = supabase.table("transactions").select("id, amount, status, risk_level, payer_id, created_at").eq("merchant_id", merchant_id).gte("created_at", today_start).execute()

    total_collections = sum(t["amount"] for t in (txns_today.data or []) if t["status"] == "captured")
    successful_count = len([t for t in (txns_today.data or []) if t["status"] == "captured"])
    pending_count = len([t for t in (txns_today.data or []) if t["status"] in ["pending", "created"]])

    suspicious_claims = []
    high_risk_today = [t for t in (txns_today.data or []) if t.get("risk_level") == "HIGH"]
    for t in high_risk_today[:5]:
        payer = supabase.table("users").select("name").eq("id", t["payer_id"]).single().execute()
        suspicious_claims.append(SuspiciousClaim(
            transaction_id=t["id"],
            amount=t["amount"],
            customer_name=payer.data["name"] if payer.data else "Unknown",
            claimed_at=t["created_at"],
            risk_level=t.get("risk_level", "HIGH"),
        ))

    risk_alerts = []
    for t in high_risk_today[:5]:
        risk_alerts.append(RiskAlert(
            transaction_id=t["id"],
            type="HIGH_RISK_PAYMENT",
            message=f"High risk payment of ₹{t['amount']/100:.0f} received",
            severity="HIGH",
            created_at=t["created_at"],
        ))

    return VendorDashboardResponse(
        today_collections=total_collections,
        successful_count=successful_count,
        pending_count=pending_count,
        suspicious_claims=suspicious_claims,
        risk_alerts=risk_alerts,
    )


@router.get("/payments", response_model=TransactionListResponse)
async def vendor_payments(
    user_id: str = Depends(get_current_user_id),
    limit: int = 20,
    offset: int = 0,
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    supabase = get_supabase_admin()
    merchant_id = await get_merchant_id(user_id)

    query = supabase.table("transactions").select("*", count="exact").eq("merchant_id", merchant_id).order("created_at", desc=True).range(offset, offset + limit - 1)
    if status:
        query = query.eq("status", status)
    if date_from:
        query = query.gte("created_at", date_from)
    if date_to:
        query = query.lte("created_at", date_to)

    result = query.execute()

    return TransactionListResponse(
        transactions=[TransactionResponse(**t) for t in (result.data or [])],
        total=result.count or 0,
    )


@router.get("/payment-verification/{payment_id}", response_model=PaymentVerificationResponse)
async def verify_payment(
    payment_id: str,
    user_id: str = Depends(get_current_user_id),
):
    supabase = get_supabase_admin()
    merchant_id = await get_merchant_id(user_id)

    txn = supabase.table("transactions").select("*").eq("razorpay_payment_id", payment_id).eq("merchant_id", merchant_id).order("created_at", desc=True).limit(1).execute()

    if txn.data and txn.data[0]["status"] == "captured":
        txn_data = txn.data[0]
        return PaymentVerificationResponse(
            verified=True,
            payment_id=payment_id,
            amount=txn_data["amount"],
            status=txn_data["status"],
            captured_at=txn_data.get("updated_at"),
            risk_level=txn_data.get("risk_level"),
            message="Payment verified successfully",
        )

    try:
        payment = await razorpay_service.fetch_payment(payment_id)
        if payment.status == "captured":
            return PaymentVerificationResponse(
                verified=True,
                payment_id=payment_id,
                amount=payment.amount,
                status=payment.status,
                captured_at=payment.captured_at,
                risk_level=None,
                message="Payment verified with Razorpay",
            )
        return PaymentVerificationResponse(
            verified=False,
            payment_id=payment_id,
            amount=payment.amount,
            status=payment.status,
            captured_at=None,
            risk_level=None,
            message="Payment not captured or not found",
        )
    except Exception:
        return PaymentVerificationResponse(
            verified=False,
            payment_id=payment_id,
            amount=None,
            status=None,
            captured_at=None,
            risk_level=None,
            message="No matching successful payment found. Do not release the order.",
        )


@router.post("/payment-verification", response_model=PaymentVerificationResponse)
async def verify_payment_by_details(
    request: PaymentVerificationRequest,
    user_id: str = Depends(get_current_user_id),
):
    supabase = get_supabase_admin()
    merchant_id = await get_merchant_id(user_id)

    query = supabase.table("transactions").select("*").eq("merchant_id", merchant_id)

    if request.amount:
        query = query.eq("amount", request.amount)
    if request.customer_phone:
        user_resp = supabase.table("users").select("id").eq("phone", request.customer_phone).execute()
        if user_resp.data:
            query = query.eq("payer_id", user_resp.data[0]["id"])

    if request.payment_id:
        query = query.eq("razorpay_payment_id", request.payment_id)

    query = query.order("created_at", desc=True).limit(1)
    result = query.execute()

    if result.data and result.data[0]["status"] == "captured":
        txn = result.data[0]
        return PaymentVerificationResponse(
            verified=True,
            payment_id=txn.get("razorpay_payment_id"),
            amount=txn["amount"],
            status=txn["status"],
            captured_at=txn.get("updated_at"),
            risk_level=txn.get("risk_level"),
            message="Payment verified successfully",
        )

    return PaymentVerificationResponse(
        verified=False,
        payment_id=request.payment_id,
        amount=request.amount,
        status=None,
        captured_at=None,
        risk_level=None,
        message="No matching successful payment found. Do not release the order.",
    )