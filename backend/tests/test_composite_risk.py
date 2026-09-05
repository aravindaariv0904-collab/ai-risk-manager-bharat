import pytest
from app.risk.engine import (
    RiskAggregator,
    RuleEngine,
    TransactionContext,
    RiskEngine,
    CompositeRiskResult,
    CATEGORY_IDENTITY_TRUST,
    CATEGORY_TRANSACTION_ANOMALY,
    CATEGORY_BEHAVIORAL_ANOMALY,
    CATEGORY_VELOCITY_NETWORK,
    CATEGORY_ML_ANOMALY,
    CATEGORY_MAX_SCORES,
    TOTAL_MAX_SCORE,
)
from app.models import RiskLevel, RiskAction, SignalSeverity
from app.schemas import RiskReason, CategoryScores, CompositeRiskOutput


def create_mock_context(**kwargs) -> TransactionContext:
    base = {
        "amount": 2500,
        "currency": "INR",
        "merchant_id": "merch_123",
        "payer_id": "payer_456",
        "hour": 14,
        "day_of_week": 1,
        "is_new_recipient": False,
        "is_unverified_merchant": False,
        "txn_count_1h": 1,
        "txn_count_24h": 3,
        "txn_count_7d": 12,
        "failed_count_24h": 0,
        "avg_amount": 3000.0,
        "median_amount": 2500.0,
        "p95_amount": 8000.0,
        "frequent_merchants": ["merch_123", "merch_789"],
        "typical_hours": [12, 13, 14, 15],
        "merchant_category": "Groceries",
        "merchant_category_history": ["Groceries", "Dining"],
    }
    base.update(kwargs)
    return TransactionContext(**base)


class TestCompositeRiskDimensions:
    """Tests each independent dimension cap and bounds."""

    def test_identity_trust_dimension_cap(self):
        aggregator = RiskAggregator()
        signals = [
            RiskReason(signal_name="id_new_recipient", category="identity_trust", reason="New", severity=SignalSeverity.LOW, score_impact=10),
            RiskReason(signal_name="id_unverified_recipient", category="identity_trust", reason="Unverified", severity=SignalSeverity.MEDIUM, score_impact=15),
            RiskReason(signal_name="id_extra_risk", category="identity_trust", reason="Extra", severity=SignalSeverity.HIGH, score_impact=20),
        ]
        res = aggregator.aggregate(signals)
        assert res.category_scores.identity_trust == 25  # Bounded at 25

    def test_transaction_anomaly_anti_stacking(self):
        """Amount anomaly signals must not excessively stack."""
        aggregator = RiskAggregator()
        # Three correlated amount signals
        signals = [
            RiskReason(signal_name="txn_amount_spike_3x", category="transaction_anomaly", reason="Spike 3x", severity=SignalSeverity.HIGH, score_impact=20),
            RiskReason(signal_name="txn_amount_exceeds_p95", category="transaction_anomaly", reason="Exceeds p95", severity=SignalSeverity.MEDIUM, score_impact=15),
            RiskReason(signal_name="txn_high_amount_new_recipient", category="transaction_anomaly", reason="High amount new", severity=SignalSeverity.HIGH, score_impact=20),
        ]
        res = aggregator.aggregate(signals)
        # Primary is 20, + 5 damped for multiple amount triggers = 25 max
        assert res.category_scores.transaction_anomaly == 25
        assert res.explanation_data["anti_stacking_applied"] is True

    def test_single_transaction_anomaly_no_stacking(self):
        aggregator = RiskAggregator()
        signals = [
            RiskReason(signal_name="txn_amount_exceeds_p95", category="transaction_anomaly", reason="Exceeds p95", severity=SignalSeverity.MEDIUM, score_impact=15),
        ]
        res = aggregator.aggregate(signals)
        assert res.category_scores.transaction_anomaly == 15
        assert res.score == 15

    def test_behavioral_anomaly_dimension_cap(self):
        aggregator = RiskAggregator()
        signals = [
            RiskReason(signal_name="beh_unusual_hour", category="behavioral_anomaly", reason="Unusual hour", severity=SignalSeverity.MEDIUM, score_impact=15),
            RiskReason(signal_name="beh_failed_attempts_spike", category="behavioral_anomaly", reason="Failed attempts", severity=SignalSeverity.HIGH, score_impact=20),
            RiskReason(signal_name="beh_unusual_category", category="behavioral_anomaly", reason="Unusual category", severity=SignalSeverity.LOW, score_impact=10),
        ]
        res = aggregator.aggregate(signals)
        assert res.category_scores.behavioral_anomaly == 25  # Bounded at 25

    def test_velocity_network_dimension_cap(self):
        aggregator = RiskAggregator()
        signals = [
            RiskReason(signal_name="vel_rapid_txns_1h", category="velocity_network", reason="1h surge", severity=SignalSeverity.MEDIUM, score_impact=10),
            RiskReason(signal_name="vel_excessive_txns_24h", category="velocity_network", reason="24h surge", severity=SignalSeverity.MEDIUM, score_impact=10),
        ]
        res = aggregator.aggregate(signals)
        assert res.category_scores.velocity_network == 15  # Bounded at 15

    def test_ml_anomaly_dimension_cap(self):
        aggregator = RiskAggregator()
        # ML raw score of 30 scales to 10 max
        res = aggregator.aggregate([], ml_score=30.0)
        assert res.category_scores.ml_anomaly == 10
        assert res.score == 10

        # ML raw score of 15 scales to 5
        res_half = aggregator.aggregate([], ml_score=15.0)
        assert res_half.category_scores.ml_anomaly == 5

        # ML raw score of 0 scales to 0
        res_zero = aggregator.aggregate([], ml_score=0.0)
        assert res_zero.category_scores.ml_anomaly == 0


class TestCompositeRiskThresholds:
    """Tests all boundary transitions: 0, 30, 31, 60, 61, 80, 81, 100."""

    @pytest.mark.parametrize("score, expected_level, expected_decision", [
        (0, RiskLevel.LOW, RiskAction.ALLOW),
        (15, RiskLevel.LOW, RiskAction.ALLOW),
        (30, RiskLevel.LOW, RiskAction.ALLOW),
        (31, RiskLevel.MEDIUM, RiskAction.STEP_UP_VERIFICATION),
        (45, RiskLevel.MEDIUM, RiskAction.STEP_UP_VERIFICATION),
        (60, RiskLevel.MEDIUM, RiskAction.STEP_UP_VERIFICATION),
        (61, RiskLevel.HIGH, RiskAction.HOLD_FOR_REVIEW),
        (70, RiskLevel.HIGH, RiskAction.HOLD_FOR_REVIEW),
        (80, RiskLevel.HIGH, RiskAction.HOLD_FOR_REVIEW),
        (81, RiskLevel.CRITICAL, RiskAction.BLOCK),
        (95, RiskLevel.CRITICAL, RiskAction.BLOCK),
        (100, RiskLevel.CRITICAL, RiskAction.BLOCK),
    ])
    def test_threshold_levels_and_decisions(self, score, expected_level, expected_decision):
        aggregator = RiskAggregator()
        # Inject exact score via category signals
        signals = []
        if score > 0:
            signals.append(RiskReason(
                signal_name="id_test",
                category="identity_trust",
                reason="test",
                severity=SignalSeverity.LOW,
                score_impact=min(25, score),
            ))
        remaining = score - min(25, score)
        if remaining > 0:
            signals.append(RiskReason(
                signal_name="txn_test",
                category="transaction_anomaly",
                reason="test",
                severity=SignalSeverity.LOW,
                score_impact=min(25, remaining),
            ))
        remaining = remaining - min(25, remaining)
        if remaining > 0:
            signals.append(RiskReason(
                signal_name="beh_test",
                category="behavioral_anomaly",
                reason="test",
                severity=SignalSeverity.LOW,
                score_impact=min(25, remaining),
            ))
        remaining = remaining - min(25, remaining)
        if remaining > 0:
            signals.append(RiskReason(
                signal_name="vel_test",
                category="velocity_network",
                reason="test",
                severity=SignalSeverity.LOW,
                score_impact=min(15, remaining),
            ))
        remaining = remaining - min(15, remaining)

        ml_score_input = float(remaining * 3.0) if remaining > 0 else 0.0

        res = aggregator.aggregate(signals, ml_score=ml_score_input)
        assert res.score == score
        assert res.level == expected_level
        assert res.decision == expected_decision

    def test_score_max_cap_100_with_extreme_values(self):
        aggregator = RiskAggregator()
        signals = [
            RiskReason(signal_name="id_extreme", category="identity_trust", reason="extreme", severity=SignalSeverity.HIGH, score_impact=100),
            RiskReason(signal_name="txn_extreme", category="transaction_anomaly", reason="extreme", severity=SignalSeverity.HIGH, score_impact=100),
            RiskReason(signal_name="beh_extreme", category="behavioral_anomaly", reason="extreme", severity=SignalSeverity.HIGH, score_impact=100),
            RiskReason(signal_name="vel_extreme", category="velocity_network", reason="extreme", severity=SignalSeverity.HIGH, score_impact=100),
        ]
        res = aggregator.aggregate(signals, ml_score=100.0, historical_risk=50)
        assert res.score == 100
        assert res.level == RiskLevel.CRITICAL
        assert res.decision == RiskAction.BLOCK


class TestEndToEndScenarios:
    """Tests realistic transactional flows."""

    def test_benign_trusted_merchant_transaction(self):
        engine = RiskEngine()
        ctx = create_mock_context(
            amount=1500,
            avg_amount=2000,
            is_new_recipient=False,
            is_unverified_merchant=False,
            txn_count_1h=0,
            txn_count_24h=2,
            hour=14,
        )
        reasons = engine.rule_engine.evaluate(ctx)
        features = engine.ml_detector.extract_features(ctx)
        ml_score = engine.ml_detector.predict(features)
        res = engine.aggregator.aggregate(reasons, ml_score=ml_score)

        assert res.score <= 30
        assert res.level == RiskLevel.LOW
        assert res.decision == RiskAction.ALLOW

    def test_suspicious_new_merchant_spike_transaction(self):
        engine = RiskEngine()
        ctx = create_mock_context(
            amount=25000,  # ₹250
            avg_amount=5000,  # ₹50 -> 5x spike!
            is_new_recipient=True,
            is_unverified_merchant=True,
            txn_count_1h=2,
            hour=23,  # Unusual late night hour
        )
        reasons = engine.rule_engine.evaluate(ctx)
        signal_names = [r.signal_name for r in reasons]
        assert "id_new_recipient" in signal_names
        assert "id_unverified_recipient" in signal_names
        assert "txn_amount_spike_3x" in signal_names
        assert "beh_unusual_hour" in signal_names

        features = engine.ml_detector.extract_features(ctx)
        ml_score = engine.ml_detector.predict(features)
        res = engine.aggregator.aggregate(reasons, ml_score=ml_score)

        assert 61 <= res.score <= 80
        assert res.level == RiskLevel.HIGH
        assert res.decision == RiskAction.HOLD_FOR_REVIEW

    def test_critical_fraud_attack_transaction(self):
        engine = RiskEngine()
        ctx = create_mock_context(
            amount=800000,  # ₹8,000 to new merchant
            avg_amount=1000,  # ₹10
            p95_amount=2500,
            is_new_recipient=True,
            is_unverified_merchant=True,
            txn_count_1h=8,  # Rapid velocity
            txn_count_24h=30,  # High daily velocity
            failed_count_24h=5,  # Multiple failed attempts
            hour=3,  # 3 AM
        )
        reasons = engine.rule_engine.evaluate(ctx)
        features = engine.ml_detector.extract_features(ctx)
        ml_score = engine.ml_detector.predict(features)
        res = engine.aggregator.aggregate(reasons, ml_score=ml_score)

        assert res.score >= 81
        assert res.level == RiskLevel.CRITICAL
        assert res.decision == RiskAction.BLOCK


class TestOutputPayloadStructure:
    """Verifies output JSON conforms exactly to specified contract."""

    def test_output_dict_contract(self):
        aggregator = RiskAggregator()
        signals = [
            RiskReason(signal_name="id_unverified_recipient", category="identity_trust", reason="Unverified", severity=SignalSeverity.MEDIUM, score_impact=15),
            RiskReason(signal_name="txn_amount_spike_3x", category="transaction_anomaly", reason="Spike 3x", severity=SignalSeverity.HIGH, score_impact=20),
        ]
        res = aggregator.aggregate(signals, ml_score=9.0)
        data = res.to_dict()

        # Must contain all required keys:
        assert "score" in data
        assert "level" in data
        assert "decision" in data
        assert "signals" in data
        assert "category_scores" in data
        assert "explanation_data" in data

        # Validate types and values
        assert isinstance(data["score"], int)
        assert data["level"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        assert data["decision"] in ["ALLOW", "STEP_UP_VERIFICATION", "HOLD_FOR_REVIEW", "BLOCK"]
        assert isinstance(data["signals"], list)
        assert isinstance(data["category_scores"], dict)
        assert "identity_trust" in data["category_scores"]
        assert "transaction_anomaly" in data["category_scores"]
        assert "behavioral_anomaly" in data["category_scores"]
        assert "velocity_network" in data["category_scores"]
        assert "ml_anomaly" in data["category_scores"]
        assert isinstance(data["explanation_data"], dict)
