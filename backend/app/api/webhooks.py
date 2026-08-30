from fastapi import APIRouter, Request, Header, HTTPException, status
from typing import Optional

from app.webhooks.service import webhook_service

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/razorpay")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: Optional[str] = Header(None),
):
    if not x_razorpay_signature:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing signature header")

    body = await request.body()

    result = await webhook_service.process_webhook(body, x_razorpay_signature)

    if result.get("status") == "rejected":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("error"))

    return {"received": True, **result}