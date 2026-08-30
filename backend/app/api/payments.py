from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
import structlog

from app.schemas import (
    CreateOrderRequest, CreateOrderResponse,
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
    The transaction must have been pre-created via /api/risk/precheck.
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

    # In demo mode with placeholder keys, return a mock order
    if settings.RAZORPAY_KEY_ID.endswith("placeholder"):
        import uuid
        mock_order_id = f"order_DEMO_{uuid.uuid4().hex[:12].upper()}"

        # Update the most recent pending transaction for this payer+merchant
        _update_transaction_order_id(supabase, payer_id, str(request.merchant_id), mock_order_id)

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
        _update_transaction_order_id(supabase, payer_id, str(request.merchant_id), order.order_id)

        logger.info("Razorpay order created", order_id=order.order_id, amount=request.amount)
        return order

    except Exception as e:
        logger.error("Order creation failed", error=str(e))
        raise HTTPException(status_code=502, detail="Payment gateway unavailable. Please try again.")


def _update_transaction_order_id(supabase, payer_id: str, merchant_id: str, order_id: str) -> None:
    """Update the most recent 'created' transaction for this payer+merchant with the Razorpay order ID."""
    try:
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