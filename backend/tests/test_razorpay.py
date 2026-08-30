import hashlib
import hmac
import json
import pytest
from app.razorpay.service import RazorpayService


@pytest.fixture
def service():
    return RazorpayService()


class TestWebhookSignature:
    def test_valid_signature_verified(self, service):
        body = json.dumps({"event": "payment.captured", "id": "evt_123"}).encode()
        expected = hmac.new(
            service.webhook_secret.encode(), body, hashlib.sha256
        ).hexdigest()
        assert service.verify_webhook_signature(body, expected) is True

    def test_invalid_signature_rejected(self, service):
        body = json.dumps({"event": "payment.captured"}).encode()
        assert service.verify_webhook_signature(body, "not_a_valid_signature") is False

    def test_tampered_body_rejected(self, service):
        body = json.dumps({"event": "payment.captured", "id": "evt_123"}).encode()
        signature = hmac.new(
            service.webhook_secret.encode(), body, hashlib.sha256
        ).hexdigest()

        tampered_body = json.dumps({"event": "payment.captured", "id": "evt_999"}).encode()
        assert service.verify_webhook_signature(tampered_body, signature) is False

    def test_empty_body_rejected(self, service):
        assert service.verify_webhook_signature(b"", "some_signature") is False

    def test_signature_is_constant_time(self, service):
        body = json.dumps({"event": "payment.captured"}).encode()
        sig_a = hmac.new(service.webhook_secret.encode(), body, hashlib.sha256).hexdigest()
        sig_b = hmac.new(("wrong_secret_" + service.webhook_secret).encode(), body, hashlib.sha256).hexdigest()
        assert service.verify_webhook_signature(body, sig_a)
        assert not service.verify_webhook_signature(body, sig_b)


class TestPaymentSignature:
    def test_valid_payment_signature(self, service):
        import os
        from app.config import settings
        secret = settings.RAZORPAY_KEY_SECRET
        payment_id = "pay_test123"
        order_id = "order_test456"
        signature = hmac.new(
            secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256
        ).hexdigest()
        assert service.verify_payment_signature(payment_id, order_id, signature) is True


class TestWebhookParsing:
    def test_payment_captured_payload(self, service):
        payload = {
            "event": "payment.captured",
            "id": "evt_987",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_123",
                        "order_id": "order_456",
                        "amount": 85000,
                        "currency": "INR",
                        "status": "captured",
                        "method": "upi",
                        "email": "test@example.com",
                        "contact": "+919876543210",
                    }
                },
                "order": {"entity": {"id": "order_456"}},
            },
        }
        parsed = service.parse_webhook_payload(payload)
        assert parsed["event"] == "payment.captured"
        assert parsed["payment_id"] == "pay_123"
        assert parsed["order_id"] == "order_456"
        assert parsed["amount"] == 85000
        assert parsed["status"] == "captured"
        assert parsed["method"] == "upi"

    def test_payment_failed_payload(self, service):
        payload = {
            "event": "payment.failed",
            "id": "evt_988",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_fail_1",
                        "order_id": "order_789",
                        "amount": 1000,
                        "currency": "INR",
                        "status": "failed",
                        "error_code": "BAD_REQUEST_ERROR",
                    }
                }
            },
        }
        parsed = service.parse_webhook_payload(payload)
        assert parsed["event"] == "payment.failed"
        assert parsed["status"] == "failed"
        assert parsed["error_code"] == "BAD_REQUEST_ERROR"

    def test_missing_payload_fields(self, service):
        payload = {"event": "order.paid"}
        parsed = service.parse_webhook_payload(payload)
        assert parsed["payment_id"] is None
        assert parsed["amount"] is None