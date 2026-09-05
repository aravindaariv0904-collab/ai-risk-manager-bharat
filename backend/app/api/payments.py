from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from datetime import datetime
import hmac
import hashlib
import structlog

from app.schemas import (
    CreateOrderRequest, CreateOrderResponse,
    VerifyPaymentRequest, VerifyPaymentResponse,
    PaymentStatusResponse,
)
from app.security.auth import get_current_user_id
from app.razorpay.service import razorpay_service
from app.services.supabase_client import get_supabase_admin
from app.config import settings

router = APIRouter(prefix="/api/payments", tags=["payments"])
logger = structlog.get_logger()


@router.post("/create-order", response_model=CreateOrderResponse)
async def create_order(
    request: CreateOrderRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    Create a Razorpay order and update the transaction record with the order ID.
    """
    supabase = get_supabase_admin()

    user_resp = supabase.table("users").select("id").eq("auth_user_id", user_id).maybe_single().execute()
    if not user_resp.data:
        raise HTTPException(status_code=404, detail="User profile not found")
    payer_id = user_resp.data["id"]

    merchant_resp = supabase.table("merchants").select("id").eq("id", str(request.merchant_id)).maybe_single().execute()
    if not merchant_resp.data:
        raise HTTPException(status_code=404, detail="Merchant not found")

    receipt = f"pay_{payer_id[:8]}_{str(request.merchant_id)[:8]}"

    # Backend is source of truth: Verify transaction risk policy before creating payment order
    if request.transaction_id:
        txn_check = (
            supabase.table("transactions")
            .select("id, risk_action, risk_score, risk_level")
            .eq("id", str(request.transaction_id))
            .maybe_single()
            .execute()
        )
        if txn_check.data:
            risk_act = txn_check.data.get("risk_action")
            risk_score = txn_check.data.get("risk_score") or 0
            if risk_act == "BLOCK" or risk_score > settings.RISK_THRESHOLD_HIGH_MAX:
                logger.warning(
                    "Blocked order creation attempt",
                    transaction_id=str(request.transaction_id),
                    risk_score=risk_score,
                    payer_id=payer_id,
                )
                raise HTTPException(
                    status_code=403,
                    detail="Payment creation blocked by risk engine security policy (Critical Risk).",
                )
            if risk_act == "HOLD_FOR_REVIEW":
                logger.warning(
                    "Held order creation attempt without manual approval",
                    transaction_id=str(request.transaction_id),
                    risk_score=risk_score,
                    payer_id=payer_id,
                )
                raise HTTPException(
                    status_code=403,
                    detail="Payment is currently held for manual review and cannot be processed directly.",
                )

    # In demo mode with placeholder keys, return a mock order
    if settings.RAZORPAY_KEY_ID.endswith("placeholder"):
        import uuid
        mock_order_id = f"order_DEMO_{uuid.uuid4().hex[:12].upper()}"

        _update_transaction_order_id(
            supabase, payer_id, str(request.merchant_id), mock_order_id,
            txn_id_hint=str(request.transaction_id) if request.transaction_id else None
        )

        logger.info("Demo order created", order_id=mock_order_id, payer=payer_id)
        return CreateOrderResponse(
            order_id=mock_order_id,
            amount=request.amount,
            currency=request.currency,
            key_id="rzp_test_demo",
            receipt=receipt,
        )

    try:
        order = await razorpay_service.create_order(
            amount=request.amount,
            currency=request.currency,
            receipt=receipt,
        )

        # Link the order to the pending transaction
        _update_transaction_order_id(
            supabase, payer_id, str(request.merchant_id), order.order_id,
            txn_id_hint=str(request.transaction_id) if request.transaction_id else None
        )

        logger.info("Razorpay order created", order_id=order.order_id, amount=request.amount)
        return order

    except Exception as e:
        logger.error("Order creation failed", error=str(e))
        raise HTTPException(status_code=502, detail="Payment gateway unavailable. Please try again.")


@router.post("/verify", response_model=VerifyPaymentResponse)
async def verify_payment(
    request: VerifyPaymentRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    Verify the client-side Razorpay payment signature via HMAC-SHA256.
    Updates the transaction status to captured upon success.
    """
    supabase = get_supabase_admin()

    # 1. Demo Mode Verification
    if settings.RAZORPAY_KEY_ID.endswith("placeholder") or request.razorpay_order_id.startswith("order_DEMO_"):
        _mark_transaction_captured(supabase, request.razorpay_payment_id, request.razorpay_order_id, request.transaction_id)
        return VerifyPaymentResponse(
            verified=True,
            status="captured",
            payment_id=request.razorpay_payment_id,
            order_id=request.razorpay_order_id,
            message="Demo payment verified and captured successfully",
        )

    # 2. Cryptographic HMAC-SHA256 verification against Razorpay secret
    msg = f"{request.razorpay_order_id}|{request.razorpay_payment_id}".encode("utf-8")
    expected_signature = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode("utf-8"),
        msg,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, request.razorpay_signature):
        logger.warning("Invalid payment signature", order_id=request.razorpay_order_id, payment_id=request.razorpay_payment_id)
        raise HTTPException(status_code=400, detail="Invalid payment signature. Payment verification failed.")

    _mark_transaction_captured(supabase, request.razorpay_payment_id, request.razorpay_order_id, request.transaction_id)

    logger.info("Payment signature verified successfully", order_id=request.razorpay_order_id, payment_id=request.razorpay_payment_id)
    return VerifyPaymentResponse(
        verified=True,
        status="captured",
        payment_id=request.razorpay_payment_id,
        order_id=request.razorpay_order_id,
        message="Payment verified and captured successfully",
    )


def _mark_transaction_captured(supabase, payment_id: str, order_id: str, transaction_id=None):
    """Mark transaction captured and record payment ID."""
    try:
        query = supabase.table("transactions")
        if transaction_id:
            query = query.eq("id", str(transaction_id))
        elif order_id:
            query = query.eq("razorpay_order_id", order_id)
        else:
            query = query.eq("razorpay_payment_id", payment_id)

        update_data = {
            "status": "captured",
            "razorpay_payment_id": payment_id,
            "updated_at": datetime.utcnow().isoformat(),
        }
        query.update(update_data).execute()
    except Exception as e:
        logger.warning("Failed to mark transaction captured", error=str(e))


def _update_transaction_order_id(supabase, payer_id: str, merchant_id: str, order_id: str, txn_id_hint: Optional[str] = None) -> None:
    """Update the transaction record with the Razorpay order ID."""
    try:
        if txn_id_hint:
            supabase.table("transactions").update({
                "razorpay_order_id": order_id,
                "status": "pending",
            }).eq("id", txn_id_hint).execute()
            return

        result = (
            supabase.table("transactions")
            .select("id")
            .eq("payer_id", payer_id)
            .eq("merchant_id", merchant_id)
            .eq("status", "created")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if result.data:
            txn_id = result.data[0]["id"]
            supabase.table("transactions").update({
                "razorpay_order_id": order_id,
                "status": "pending",
            }).eq("id", txn_id).execute()
    except Exception as e:
        logger.warning("Failed to update transaction order_id", error=str(e))


@router.get("/{payment_id}/status", response_model=PaymentStatusResponse)
async def get_payment_status(
    payment_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Fetch real payment status from Razorpay. Never trust client-side claims."""
    # Demo mode: check DB first
    supabase = get_supabase_admin()
    txn = supabase.table("transactions").select("*").eq("razorpay_payment_id", payment_id).maybe_single().execute()
    if txn.data:
        return PaymentStatusResponse(
            payment_id=payment_id,
            order_id=txn.data.get("razorpay_order_id"),
            amount=txn.data.get("amount"),
            status=txn.data.get("status"),
        )

    if settings.RAZORPAY_KEY_ID.endswith("placeholder"):
        raise HTTPException(status_code=404, detail="Payment not found (demo mode — no real Razorpay key)")

    try:
        payment = await razorpay_service.fetch_payment(payment_id)
        return payment
    except Exception as e:
        logger.error("Payment status fetch failed", payment_id=payment_id, error=str(e))
        raise HTTPException(status_code=404, detail="Payment not found")