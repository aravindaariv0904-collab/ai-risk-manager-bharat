from fastapi import APIRouter, Request, Header, HTTPException, status
from typing import Optional

from app.webhooks.service import webhook_service

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/razorpay")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: Optional[str] = Header(None, alias="X-Razorpay-Signature"),
    x_razorpay_event_id: Optional[str] = Header(None, alias="X-Razorpay-Event-Id"),
):
    """
    Ingest Razorpay webhook notifications.
    Validates X-Razorpay-Signature, enforces idempotency via X-Razorpay-Event-Id,
    and transitions transactions reliably.
    """
    if not x_razorpay_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing signature header (X-Razorpay-Signature required)",
        )

    body = await request.body()

    try:
        result = await webhook_service.process_webhook(
            payload=body,
            signature=x_razorpay_signature,
            event_id_header=x_razorpay_event_id,
        )
    except Exception as exc:
        # Never let a DB/network error inside the service propagate as an unhandled 500.
        # Return 503 so Razorpay can retry.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Webhook processing temporarily unavailable: {exc}",
        )

    if result.get("status") == "rejected":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("error"))

    return {"received": True, **result}