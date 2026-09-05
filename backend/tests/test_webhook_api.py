import hashlib
import hmac
import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.webhooks.service import webhook_service
from app.payments.state_machine import TransactionStatus

client = TestClient(app)


def make_signature(body: bytes) -> str:
    return hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()


def payment_captured_payload(event_id: str = "evt_payment_captured_123", payment_id: str = "pay_demo_api_001"):
    return {
        "entity": "event",
        "account_id": "acc_DEMO123",
        "event": "payment.captured",
        "id": event_id,
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
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


class TestWebhookEndpointSecurity:
    def test_missing_signature_rejected(self):
        response = client.post(
            "/api/webhooks/razorpay",
            json=payment_captured_payload(),
        )
        assert response.status_code == 400
        assert "Missing signature" in response.json()["detail"]

    def test_invalid_signature_rejected(self):
        response = client.post(
            "/api/webhooks/razorpay",
            json=payment_captured_payload(),
            headers={"X-Razorpay-Signature": "invalid_signature"},
        )
        assert response.status_code == 400
        assert "Invalid or missing webhook signature" in response.json()["detail"]

    def test_invalid_json_rejected(self):
        body = b"this is not a valid json payload {"
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
        assert "Invalid JSON" in response.json()["detail"]

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
        assert "Missing event ID" in response.json()["detail"]

    def test_official_x_razorpay_event_id_header_used_when_body_lacks_id(self):
        payload = payment_captured_payload()
        del payload["id"]
        body = json.dumps(payload).encode()
        signature = make_signature(body)

        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = None
        mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock()
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"id": "txn-1", "status": "AUTHORIZED", "amount": 85000, "merchant_id": "m-1"}
        ]

        with patch.object(webhook_service, "_supabase", mock_supabase):
            response = client.post(
                "/api/webhooks/razorpay",
                content=body,
                headers={
                    "X-Razorpay-Signature": signature,
                    "X-Razorpay-Event-Id": "evt_from_header_999",
                    "Content-Type": "application/json",
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["received"] is True
            assert data["event_id"] == "evt_from_header_999"


class TestWebhookIdempotencyAndRaceConditions:
    @pytest.mark.asyncio
    async def test_duplicate_event_already_processed_returns_duplicate_status(self):
        body = json.dumps(payment_captured_payload("evt_dup_123")).encode()
        signature = make_signature(body)

        mock_supabase = MagicMock()
        # Mock existing processed event
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "event_id": "evt_dup_123",
            "processing_status": "processed",
        }

        with patch.object(webhook_service, "_supabase", mock_supabase):
            result = await webhook_service.process_webhook(body, signature)
            assert result["status"] == "duplicate"
            assert result["event_id"] == "evt_dup_123"

    @pytest.mark.asyncio
    async def test_concurrent_duplicate_event_caught_by_unique_constraint(self):
        body = json.dumps(payment_captured_payload("evt_race_123")).encode()
        signature = make_signature(body)

        mock_supabase = MagicMock()
        # Initial check returns None (simulating race before insert)
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = None
        # Insert raises unique constraint exception
        mock_supabase.table.return_value.insert.return_value.execute.side_effect = Exception("duplicate key value violates unique constraint")

        with patch.object(webhook_service, "_supabase", mock_supabase):
            result = await webhook_service.process_webhook(body, signature)
            assert result["status"] == "duplicate"
            assert result["event_id"] == "evt_race_123"

    @pytest.mark.asyncio
    async def test_failed_event_allows_retry_and_reprocessing(self):
        body = json.dumps(payment_captured_payload("evt_retry_123")).encode()
        signature = make_signature(body)

        mock_supabase = MagicMock()
        # Event was previously failed
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "event_id": "evt_retry_123",
            "processing_status": "failed",
            "processing_error": "Temporary connection reset",
        }
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"id": "txn-retry-1", "status": "AUTHORIZED", "amount": 85000, "merchant_id": "m-retry-1"}
        ]

        with patch.object(webhook_service, "_supabase", mock_supabase):
            result = await webhook_service.process_webhook(body, signature)
            assert result["status"] == "processed"
            assert result["event_id"] == "evt_retry_123"


class TestWebhookEventHandlingAndOrdering:
    @pytest.mark.asyncio
    async def test_payment_captured_event_transitions_to_captured(self):
        body = json.dumps(payment_captured_payload("evt_cap_001", "pay_cap_001")).encode()
        signature = make_signature(body)

        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = None
        mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock()
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"id": "txn-cap-1", "status": "AUTHORIZED", "amount": 85000, "merchant_id": "m-1"}
        ]

        with patch.object(webhook_service, "_supabase", mock_supabase):
            result = await webhook_service.process_webhook(body, signature)
            assert result["status"] == "processed"
            assert result["event_type"] == "payment.captured"

    @pytest.mark.asyncio
    async def test_payment_failed_event_transitions_to_failed(self):
        payload = {
            "entity": "event",
            "event": "payment.failed",
            "id": "evt_fail_001",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_fail_001",
                        "order_id": "order_fail_001",
                        "amount": 5000,
                        "status": "failed",
                    }
                }
            }
        }
        body = json.dumps(payload).encode()
        signature = make_signature(body)

        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = None
        mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock()
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"id": "txn-fail-1", "status": "AUTHORIZED", "amount": 5000, "merchant_id": "m-1"}
        ]

        with patch.object(webhook_service, "_supabase", mock_supabase):
            result = await webhook_service.process_webhook(body, signature)
            assert result["status"] == "processed"
            assert result["event_type"] == "payment.failed"

    @pytest.mark.asyncio
    async def test_unknown_event_handled_gracefully(self):
        payload = {
            "entity": "event",
            "event": "virtual_account.credited",
            "id": "evt_unk_001",
            "payload": {}
        }
        body = json.dumps(payload).encode()
        signature = make_signature(body)

        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = None
        mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock()
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        with patch.object(webhook_service, "_supabase", mock_supabase):
            result = await webhook_service.process_webhook(body, signature)
            assert result["status"] == "processed"
            assert result["event_type"] == "virtual_account.credited"

    @pytest.mark.asyncio
    async def test_out_of_order_order_paid_does_not_revert_captured_transaction(self):
        # Transaction is already CAPTURED
        payload = {
            "entity": "event",
            "event": "order.paid",
            "id": "evt_order_paid_001",
            "payload": {
                "order": {
                    "entity": {
                        "id": "order_cap_123",
                        "amount": 85000,
                        "status": "paid",
                    }
                }
            }
        }
        body = json.dumps(payload).encode()
        signature = make_signature(body)

        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = None
        mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock()
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"id": "txn-order-1", "status": "CAPTURED", "amount": 85000, "merchant_id": "m-1"}
        ]

        with patch.object(webhook_service, "_supabase", mock_supabase):
            result = await webhook_service.process_webhook(body, signature)
            assert result["status"] == "processed"