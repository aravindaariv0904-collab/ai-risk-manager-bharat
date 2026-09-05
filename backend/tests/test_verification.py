import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.models import RiskLevel, RiskAction
from app.payments.verification import verification_service, VerificationStatus
from app.payments.state_machine import TransactionStatus
from app.security.auth import get_current_user_id

client = TestClient(app)


@pytest.fixture(autouse=True)
def override_auth():
    app.dependency_overrides[get_current_user_id] = lambda: "auth-uuid-1"
    yield
    app.dependency_overrides.pop(get_current_user_id, None)


class TestRiskAdaptiveVerificationRequirements:
    def test_low_risk_no_verification_needed(self):
        policy = verification_service.evaluate_verification_requirement(RiskLevel.LOW, RiskAction.ALLOW)
        assert policy["required"] is False
        assert policy["action"] == "ALLOW"

    def test_medium_risk_requires_otp_step_up(self):
        policy = verification_service.evaluate_verification_requirement(RiskLevel.MEDIUM, RiskAction.STEP_UP_VERIFICATION)
        assert policy["required"] is True
        assert policy["challenge_type"] == "OTP_STEP_UP"

    def test_high_risk_requires_manual_compliance_review(self):
        policy = verification_service.evaluate_verification_requirement(RiskLevel.HIGH, RiskAction.HOLD_FOR_REVIEW)
        assert policy["required"] is True
        assert policy["challenge_type"] == "MANUAL_COMPLIANCE_REVIEW"

    def test_critical_risk_is_blocked(self):
        policy = verification_service.evaluate_verification_requirement(RiskLevel.CRITICAL, RiskAction.BLOCK)
        assert policy["required"] is False
        assert policy["action"] == "BLOCK"


class TestVerificationLifecycleAndBypassPrevention:
    @pytest.mark.asyncio
    async def test_successful_verification_flow(self):
        txn_id = "00000000-0000-0000-0000-000000000010"
        challenge_id = "00000000-0000-0000-0000-000000000011"
        now = datetime.utcnow()

        mock_supabase = MagicMock()
        # Mock transaction in VERIFICATION_REQUIRED
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.side_effect = [
            MagicMock(data={"id": txn_id, "status": TransactionStatus.VERIFICATION_REQUIRED.value}),
            MagicMock(data={
                "id": challenge_id,
                "transaction_id": txn_id,
                "status": VerificationStatus.PENDING,
                "attempts": 0,
                "max_attempts": 3,
                "challenge_token": "654321",
                "expires_at": (now + timedelta(minutes=5)).isoformat(),
            }),
        ]
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data={
            "id": challenge_id,
            "transaction_id": txn_id,
            "status": VerificationStatus.PENDING,
            "attempts": 0,
            "max_attempts": 3,
            "challenge_token": "654321",
            "expires_at": (now + timedelta(minutes=5)).isoformat(),
        })
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock()

        with patch.object(verification_service, "_supabase", mock_supabase):
            res = await verification_service.verify_challenge(txn_id, challenge_id, "654321")
            assert res["verified"] is True
            assert res["status"] == VerificationStatus.VERIFIED
            assert res["transaction_status"] == TransactionStatus.RISK_CHECKED.value

    @pytest.mark.asyncio
    async def test_failed_verification_attempt_decrements_remaining(self):
        txn_id = "00000000-0000-0000-0000-000000000020"
        challenge_id = "00000000-0000-0000-0000-000000000021"
        now = datetime.utcnow()

        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data={
            "id": challenge_id,
            "transaction_id": txn_id,
            "status": VerificationStatus.PENDING,
            "attempts": 0,
            "max_attempts": 3,
            "challenge_token": "999888",
            "expires_at": (now + timedelta(minutes=5)).isoformat(),
        })
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        with patch.object(verification_service, "_supabase", mock_supabase):
            with pytest.raises(ValueError) as exc:
                await verification_service.verify_challenge(txn_id, challenge_id, "000000")
            assert "2 attempt(s) remaining" in str(exc.value)

    @pytest.mark.asyncio
    async def test_repeated_failed_attempts_locks_transaction(self):
        txn_id = "00000000-0000-0000-0000-000000000030"
        challenge_id = "00000000-0000-0000-0000-000000000031"
        now = datetime.utcnow()

        mock_supabase = MagicMock()
        # Challenge with 2 previous attempts
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data={
            "id": challenge_id,
            "transaction_id": txn_id,
            "status": VerificationStatus.PENDING,
            "attempts": 2,
            "max_attempts": 3,
            "challenge_token": "999888",
            "expires_at": (now + timedelta(minutes=5)).isoformat(),
        })
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        with patch.object(verification_service, "_supabase", mock_supabase):
            with pytest.raises(ValueError) as exc:
                await verification_service.verify_challenge(txn_id, challenge_id, "000000")
            assert "Maximum attempts exceeded" in str(exc.value)

    @pytest.mark.asyncio
    async def test_expired_challenge_is_rejected(self):
        txn_id = "00000000-0000-0000-0000-000000000040"
        challenge_id = "00000000-0000-0000-0000-000000000041"
        now = datetime.utcnow()

        mock_supabase = MagicMock()
        # Challenge expired 10 minutes ago
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data={
            "id": challenge_id,
            "transaction_id": txn_id,
            "status": VerificationStatus.PENDING,
            "attempts": 0,
            "max_attempts": 3,
            "challenge_token": "123456",
            "expires_at": (now - timedelta(minutes=10)).isoformat(),
        })
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        with patch.object(verification_service, "_supabase", mock_supabase):
            with pytest.raises(ValueError) as exc:
                await verification_service.verify_challenge(txn_id, challenge_id, "123456")
            assert "expired" in str(exc.value).lower()
