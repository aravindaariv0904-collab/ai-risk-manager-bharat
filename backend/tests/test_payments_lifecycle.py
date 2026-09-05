import hmac
import hashlib
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.security.auth import get_current_user_id
from app.payments.state_machine import TransactionStatus

client = TestClient(app)


@pytest.fixture(autouse=True)
def override_auth():
    app.dependency_overrides[get_current_user_id] = lambda: "auth-uuid-1"
    yield
    app.dependency_overrides.pop(get_current_user_id, None)


class TestPaymentLifecycleAndRiskGating:
    def test_block_action_rejects_order_creation_with_403(self):
        mock_supabase = MagicMock()
        # Mock user profile, merchant, and blocked transaction
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.side_effect = [
            MagicMock(data={"id": "user-uuid-1", "auth_user_id": "auth-uuid-1"}), # user
            MagicMock(data={"id": "merch-uuid-1"}), # merchant
            MagicMock(data={"id": "txn-blocked-1", "risk_action": "BLOCK", "risk_score": 85, "risk_level": "CRITICAL"}), # txn
        ]

        with patch("app.api.payments.get_supabase_admin", return_value=mock_supabase):
            response = client.post(
                "/api/payments/create-order",
                json={
                    "amount": 50000,
                    "currency": "INR",
                    "merchant_id": "00000000-0000-0000-0000-000000000001",
                    "transaction_id": "00000000-0000-0000-0000-000000000002",
                },
                headers={"Authorization": "Bearer test_token"},
            )
            assert response.status_code == 403
            assert "blocked" in response.json()["detail"].lower()

    def test_hold_for_review_action_rejects_order_creation_with_403(self):
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.side_effect = [
            MagicMock(data={"id": "user-uuid-1", "auth_user_id": "auth-uuid-1"}),
            MagicMock(data={"id": "merch-uuid-1"}),
            MagicMock(data={"id": "txn-held-1", "risk_action": "HOLD_FOR_REVIEW", "risk_score": 70, "risk_level": "HIGH"}),
        ]

        with patch("app.api.payments.get_supabase_admin", return_value=mock_supabase):
            response = client.post(
                "/api/payments/create-order",
                json={
                    "amount": 25000,
                    "currency": "INR",
                    "merchant_id": "00000000-0000-0000-0000-000000000001",
                    "transaction_id": "00000000-0000-0000-0000-000000000003",
                },
                headers={"Authorization": "Bearer test_token"},
            )
            assert response.status_code == 403
            assert "held" in response.json()["detail"].lower()

    def test_allow_action_proceeds_with_order_creation(self):
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.side_effect = [
            MagicMock(data={"id": "user-uuid-1", "auth_user_id": "auth-uuid-1"}),
            MagicMock(data={"id": "merch-uuid-1"}),
            MagicMock(data={"id": "txn-ok-1", "risk_action": "ALLOW", "risk_score": 15, "risk_level": "LOW", "status": "RISK_CHECKED"}),
        ]
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        with patch("app.api.payments.get_supabase_admin", return_value=mock_supabase):
            response = client.post(
                "/api/payments/create-order",
                json={
                    "amount": 1000,
                    "currency": "INR",
                    "merchant_id": "00000000-0000-0000-0000-000000000001",
                    "transaction_id": "00000000-0000-0000-0000-000000000004",
                },
                headers={"Authorization": "Bearer test_token"},
            )
            assert response.status_code == 200
            data = response.json()
            assert "order_id" in data
            assert data["amount"] == 1000

    def test_payment_verify_invalid_signature_rejected(self):
        with patch.object(settings, "RAZORPAY_KEY_ID", "rzp_live_abc123"), \
             patch.object(settings, "RAZORPAY_KEY_SECRET", "secret_key_xyz"):
            response = client.post(
                "/api/payments/verify",
                json={
                    "razorpay_payment_id": "pay_real_001",
                    "razorpay_order_id": "order_real_001",
                    "razorpay_signature": "invalid_tampered_signature",
                },
                headers={"Authorization": "Bearer test_token"},
            )
            assert response.status_code == 400
            assert "Invalid payment signature" in response.json()["detail"]

    def test_payment_verify_valid_signature_captures_transaction(self):
        secret = "secret_key_xyz"
        payment_id = "pay_valid_123"
        order_id = "order_valid_456"
        valid_signature = hmac.new(
            secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256
        ).hexdigest()

        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"id": "txn-cap-1", "status": "AUTHORIZED", "amount": 1000, "merchant_id": "m-1"}
        ]
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=None)

        with patch("app.api.payments.get_supabase_admin", return_value=mock_supabase), \
             patch.object(settings, "RAZORPAY_KEY_ID", "rzp_live_abc123"), \
             patch.object(settings, "RAZORPAY_KEY_SECRET", secret):
            response = client.post(
                "/api/payments/verify",
                json={
                    "razorpay_payment_id": payment_id,
                    "razorpay_order_id": order_id,
                    "razorpay_signature": valid_signature,
                },
                headers={"Authorization": "Bearer test_token"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["verified"] is True
            assert data["status"] == "captured"
