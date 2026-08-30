import pytest
from pydantic import ValidationError

from app.schemas import (
    RiskPrecheckRequest,
    RiskPrecheckResponse,
    CreateOrderRequest,
    ExplainRiskRequest,
    FeedbackCreate,
    RiskReason,
    RiskLevel,
    SignalSeverity,
)


class TestRiskSchemas:
    def test_precheck_valid(self):
        req = RiskPrecheckRequest(amount=85000, merchant_id="10000000-0000-0000-0000-000000000010")
        assert req.amount == 85000

    def test_precheck_zero_amount_rejected(self):
        with pytest.raises(ValidationError):
            RiskPrecheckRequest(amount=0, merchant_id="m1")

    def test_precheck_negative_amount_rejected(self):
        with pytest.raises(ValidationError):
            RiskPrecheckRequest(amount=-100, merchant_id="m1")

    def test_precheck_missing_merchant_rejected(self):
        with pytest.raises(ValidationError):
            RiskPrecheckRequest(amount=100)

    def test_precheck_invalid_merchant_format_rejected(self):
        with pytest.raises(ValidationError):
            RiskPrecheckRequest(amount=100, merchant_id="not-a-uuid")

    def test_create_order_valid(self):
        req = CreateOrderRequest(amount=1000, merchant_id="10000000-0000-0000-0000-000000000011")
        assert req.currency == "INR"

    def test_create_order_amount_too_large_rejected(self):
        with pytest.raises(ValidationError):
            CreateOrderRequest(amount=2**40, merchant_id="m1")

    def test_explain_risk_valid(self):
        req = ExplainRiskRequest(
            risk_score=84,
            risk_level=RiskLevel.HIGH,
            reasons=[
                RiskReason(
                    signal_name="amount_anomaly",
                    reason="Amount above normal",
                    severity=SignalSeverity.HIGH,
                    score_impact=20,
                )
            ],
        )
        assert req.language == "en"

    def test_explain_risk_score_out_of_range_rejected(self):
        with pytest.raises(ValidationError):
            ExplainRiskRequest(risk_score=150, risk_level=RiskLevel.HIGH, reasons=[])

    def test_feedback_valid(self):
        req = FeedbackCreate(
            transaction_id="10000000-0000-0000-0000-000000000010",
            label="legitimate",
            fraud_confirmed=False,
        )
        assert req.label == "legitimate"

    def test_feedback_invalid_label_rejected(self):
        with pytest.raises(ValidationError):
            FeedbackCreate(transaction_id="10000000-0000-0000-0000-000000000010", label="unknown")


class TestPrecheckResponse:
    def test_response_schema(self):
        reasons = [
            RiskReason(
                signal_name="test",
                reason="Test reason",
                severity=SignalSeverity.HIGH,
                score_impact=30,
            )
        ]
        resp = RiskPrecheckResponse(
            transaction_id="10000000-0000-0000-0000-000000000010",
            risk_score=84,
            risk_level=RiskLevel.HIGH,
            risk_action="WARN",
            reasons=reasons,
            recommended_action="Verify Recipient",
        )
        assert resp.risk_score == 84
        assert len(resp.reasons) == 1