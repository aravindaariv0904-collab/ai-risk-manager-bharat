import hashlib
import hmac
import json
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings


requires_supabase = pytest.mark.skipif(
    not settings.SUPABASE_URL or "placeholder" in settings.SUPABASE_URL,
    reason="Requires a real Supabase project",
)

client = TestClient(app)


def make_signature(body: bytes) -> str:
    return hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()


def payment_captured_payload():
    return {
        "entity": "event",
        "account_id": "acc_DEMO123",
        "event": "payment.captured",
        "id": "evt_payment_captured_123",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_demo_api_001",
                    "entity": "payment",
                    "amount": 85000,
                    "currency": "INR",
                    "status": "captured",
                    "order_id": "order_demo_api_001",
                    "method": "upi",
                    "captured": True,
                }
            },
            "order": {"entity": {"id": "order_demo_api_001"}},
        },
        "created_at": 1700000000,
    }


class TestWebhookEndpoint:
    def test_missing_signature_rejected(self):
        response = client.post(
            "/api/webhooks/razorpay",
            json=payment_captured_payload(),
        )
        assert response.status_code == 400

    def test_invalid_signature_rejected(self):
        response = client.post(
            "/api/webhooks/razorpay",
            json=payment_captured_payload(),
            headers={"X-Razorpay-Signature": "invalid_signature"},
        )
        assert response.status_code == 400

    @requires_supabase
    def test_valid_signature_accepted(self):
        body = json.dumps(payment_captured_payload()).encode()
        signature = make_signature(body)
        response = client.post(
            "/api/webhooks/razorpay",
            content=body,
            headers={
                "X-Razorpay-Signature": signature,
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 200
        assert response.json()["received"] is True

    def test_invalid_json_rejected(self):
        body = b"this is not json"
        signature = make_signature(body)
        response = client.post(
            "/api/webhooks/razorpay",
            content=body,
            headers={
                "X-Razorpay-Signature": signature,
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 400

    def test_missing_event_id_rejected(self):
        payload = payment_captured_payload()
        del payload["id"]
        body = json.dumps(payload).encode()
        signature = make_signature(body)
        response = client.post(
            "/api/webhooks/razorpay",
            content=body,
            headers={
                "X-Razorpay-Signature": signature,
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 400


@requires_supabase
class TestDuplicateWebhookHandling:
    def test_duplicate_webhook_event_does_not_process_twice(self):
        body = json.dumps(payment_captured_payload()).encode()
        signature = make_signature(body)

        first = client.post(
            "/api/webhooks/razorpay",
            content=body,
            headers={
                "X-Razorpay-Signature": signature,
                "Content-Type": "application/json",
            },
        )
        assert first.status_code == 200

        second = client.post(
            "/api/webhooks/razorpay",
            content=body,
            headers={
                "X-Razorpay-Signature": signature,
                "Content-Type": "application/json",
            },
        )
        assert second.status_code == 200
        assert second.json().get("status") == "duplicate"