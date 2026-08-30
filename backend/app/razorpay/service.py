import hmac
import hashlib
import json
from typing import Optional, Dict, Any
import httpx
from app.config import settings
from app.schemas import CreateOrderResponse, PaymentStatusResponse


class RazorpayService:
    BASE_URL = "https://api.razorpay.com/v1"

    def __init__(self):
        self.auth = (settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        self.key_id = settings.RAZORPAY_KEY_ID
        self.webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET

    async def create_order(self, amount: int, currency: str = "INR", receipt: Optional[str] = None) -> CreateOrderResponse:
        async with httpx.AsyncClient(auth=self.auth, timeout=30.0) as client:
            payload = {
                "amount": amount,
                "currency": currency,
                "payment_capture": 1,
            }
            if receipt:
                payload["receipt"] = receipt

            response = await client.post(f"{self.BASE_URL}/orders", json=payload)
            response.raise_for_status()
            data = response.json()

            return CreateOrderResponse(
                order_id=data["id"],
                amount=data["amount"],
                currency=data["currency"],
                key_id=self.key_id,
            )

    async def fetch_payment(self, payment_id: str) -> PaymentStatusResponse:
        async with httpx.AsyncClient(auth=self.auth, timeout=30.0) as client:
            response = await client.get(f"{self.BASE_URL}/payments/{payment_id}")
            response.raise_for_status()
            data = response.json()

            return PaymentStatusResponse(
                payment_id=data["id"],
                status=data["status"],
                amount=data["amount"],
                captured_at=data.get("captured_at"),
            )

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        expected_signature = hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected_signature, signature)

    def verify_payment_signature(self, payment_id: str, order_id: str, signature: str) -> bool:
        payload = f"{order_id}|{payment_id}".encode()
        expected_signature = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected_signature, signature)

    def parse_webhook_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        event = payload.get("event")
        payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        order_entity = payload.get("payload", {}).get("order", {}).get("entity", {})

        return {
            "event": event,
            "payment_id": payment_entity.get("id"),
            "order_id": order_entity.get("id") or payment_entity.get("order_id"),
            "amount": payment_entity.get("amount"),
            "currency": payment_entity.get("currency"),
            "status": payment_entity.get("status"),
            "captured_at": payment_entity.get("captured_at"),
            "method": payment_entity.get("method"),
            "email": payment_entity.get("email"),
            "contact": payment_entity.get("contact"),
            "fee": payment_entity.get("fee"),
            "tax": payment_entity.get("tax"),
            "error_code": payment_entity.get("error_code"),
            "error_description": payment_entity.get("error_description"),
        }


razorpay_service = RazorpayService()