import pytest
from datetime import datetime
from app.risk.engine import (
    RuleEngine, TransactionContext, RiskAggregator,
    RiskLevel, RiskAction,
    CATEGORY_IDENTITY_TRUST, CATEGORY_TRANSACTION_ANOMALY,
    CATEGORY_BEHAVIORAL_ANOMALY, CATEGORY_VELOCITY_NETWORK, CATEGORY_ML_ANOMALY,
)


def make_context(**overrides) -> TransactionContext:
    defaults = dict(
        amount=10000,
        currency="INR",
        merchant_id="m1",
        payer_id="p1",
        hour=12,
        day_of_week=2,
        is_new_recipient=False,
        is_unverified_merchant=False,
        txn_count_1h=0,
        txn_count_24h=5,
        txn_count_7d=20,
        failed_count_24h=0,
        avg_amount=5000,
        median_amount=4000,
        p95_amount=15000,
        frequent_merchants=["m1", "m2"],
        typical_hours=[10, 11, 12],
    )
    defaults.update(overrides)
    return TransactionContext(**defaults)


class TestRuleEngine:
    def test_low_risk_tx_no_rules_triggered(self):
        ctx = make_context()
        reasons = RuleEngine().evaluate(ctx)
        assert reasons == []

    def test_new_recipient_high_amount(self):
        ctx = make_context(is_new_recipient=True, amount=20000, avg_amount=4000)
        reasons = RuleEngine().evaluate(ctx)
        names = [r.signal_name for r in reasons]
        assert "txn_amount_spike_3x" in names
        assert "id_new_recipient" in names

    def test_rapid_repeated_transactions(self):
        ctx = make_context(txn_count_1h=6)
        reasons = RuleEngine().evaluate(ctx)
        names = [r.signal_name for r in reasons]
        assert "vel_rapid_txns_1h" in names

    def test_rapid_below_threshold(self):
        ctx = make_context(txn_count_1h=5)
        reasons = RuleEngine().evaluate(ctx)
        names = [r.signal_name for r in reasons]
        assert "vel_rapid_txns_1h" not in names

    def test_unusual_time_late_night(self):
        ctx = make_context(hour=3)
        reasons = RuleEngine().evaluate(ctx)
        names = [r.signal_name for r in reasons]
        assert "beh_unusual_hour" in names

    def test_unusual_time_after_11pm(self):
        ctx = make_context(hour=23)
        reasons = RuleEngine().evaluate(ctx)
        names = [r.signal_name for r in reasons]
        assert "beh_unusual_hour" in names

    def test_unusual_time_normal_hours(self):
        ctx = make_context(hour=12)
        reasons = RuleEngine().evaluate(ctx)
        names = [r.signal_name for r in reasons]
        assert "beh_unusual_hour" not in names

    def test_failed_attempts(self):
        ctx = make_context(failed_count_24h=4)
        reasons = RuleEngine().evaluate(ctx)
        names = [r.signal_name for r in reasons]
        assert "beh_failed_attempts_spike" in names

    def test_amount_anomaly_above_p95(self):
        ctx = make_context(amount=20000, p95_amount=15000)
        reasons = RuleEngine().evaluate(ctx)
        names = [r.signal_name for r in reasons]
        assert "txn_amount_exceeds_p95" in names

    def test_amount_normal_below_p95(self):
        ctx = make_context(amount=12000, p95_amount=15000)
        reasons = RuleEngine().evaluate(ctx)
        names = [r.signal_name for r in reasons]
        assert "txn_amount_exceeds_p95" not in names

    def test_empty_history_no_rules(self):
        ctx = make_context(
            avg_amount=0, median_amount=0, p95_amount=0,
            txn_count_1h=0, txn_count_24h=0,
        )
        reasons = RuleEngine().evaluate(ctx)
        assert all(r.score_impact <= 25 for r in reasons)


class TestRiskAggregator:
    def test_low_thresholds(self):
        aggregator = RiskAggregator()
        res = aggregator.aggregate([], 0, 0, 0)
        assert res.score <= 30
        assert res.level == RiskLevel.LOW
        assert res.decision == RiskAction.ALLOW

    def test_medium_thresholds(self):
        aggregator = RiskAggregator()
        from app.schemas import RiskReason, SignalSeverity
        signals = [
            RiskReason(signal_name="id_unverified_recipient", category="identity_trust", reason="test", severity=SignalSeverity.MEDIUM, score_impact=15),
            RiskReason(signal_name="txn_amount_spike_3x", category="transaction_anomaly", reason="test", severity=SignalSeverity.HIGH, score_impact=20),
        ]
        res = aggregator.aggregate(signals, 0, 0, 0)
        assert 31 <= res.score <= 60
        assert res.level == RiskLevel.MEDIUM
        assert res.decision == RiskAction.STEP_UP_VERIFICATION

    def test_high_thresholds(self):
        aggregator = RiskAggregator()
        from app.schemas import RiskReason, SignalSeverity
        signals = [
            RiskReason(signal_name="id_unverified_recipient", category="identity_trust", reason="test", severity=SignalSeverity.MEDIUM, score_impact=15),
            RiskReason(signal_name="id_new_recipient", category="identity_trust", reason="test", severity=SignalSeverity.LOW, score_impact=10),
            RiskReason(signal_name="txn_amount_spike_3x", category="transaction_anomaly", reason="test", severity=SignalSeverity.HIGH, score_impact=20),
            RiskReason(signal_name="beh_failed_attempts_spike", category="behavioral_anomaly", reason="test", severity=SignalSeverity.HIGH, score_impact=20),
        ]
        res = aggregator.aggregate(signals, 0, 0, 0)
        assert 61 <= res.score <= 80
        assert res.level == RiskLevel.HIGH
        assert res.decision == RiskAction.HOLD_FOR_REVIEW

    def test_boundary_30_is_low(self):
        aggregator = RiskAggregator()
        from app.schemas import RiskReason, SignalSeverity
        signals = [
            RiskReason(signal_name="id_unverified_recipient", category="identity_trust", reason="test", severity=SignalSeverity.MEDIUM, score_impact=15),
            RiskReason(signal_name="beh_unusual_hour", category="behavioral_anomaly", reason="test", severity=SignalSeverity.MEDIUM, score_impact=15),
        ]
        res = aggregator.aggregate(signals, 0, 0, 0)
        assert res.score == 30
        assert res.level == RiskLevel.LOW
        assert res.decision == RiskAction.ALLOW

    def test_boundary_31_is_medium(self):
        aggregator = RiskAggregator()
        from app.schemas import RiskReason, SignalSeverity
        signals = [
            RiskReason(signal_name="id_unverified_recipient", category="identity_trust", reason="test", severity=SignalSeverity.MEDIUM, score_impact=15),
            RiskReason(signal_name="beh_unusual_hour", category="behavioral_anomaly", reason="test", severity=SignalSeverity.MEDIUM, score_impact=15),
        ]
        res = aggregator.aggregate(signals, 0, 3.0, 0)  # ml contributes 1 point -> 31
        assert res.score == 31
        assert res.level == RiskLevel.MEDIUM
        assert res.decision == RiskAction.STEP_UP_VERIFICATION

    def test_boundary_60_is_medium(self):
        aggregator = RiskAggregator()
        from app.schemas import RiskReason, SignalSeverity
        signals = [
            RiskReason(signal_name="id_unverified_recipient", category="identity_trust", reason="test", severity=SignalSeverity.MEDIUM, score_impact=25),
            RiskReason(signal_name="txn_amount_spike_3x", category="transaction_anomaly", reason="test", severity=SignalSeverity.HIGH, score_impact=25),
            RiskReason(signal_name="vel_rapid_txns_1h", category="velocity_network", reason="test", severity=SignalSeverity.LOW, score_impact=10),
        ]
        res = aggregator.aggregate(signals, 0, 0, 0)
        assert res.score == 60
        assert res.level == RiskLevel.MEDIUM
        assert res.decision == RiskAction.STEP_UP_VERIFICATION

    def test_boundary_61_is_high(self):
        aggregator = RiskAggregator()
        from app.schemas import RiskReason, SignalSeverity
        signals = [
            RiskReason(signal_name="id_unverified_recipient", category="identity_trust", reason="test", severity=SignalSeverity.MEDIUM, score_impact=25),
            RiskReason(signal_name="txn_amount_spike_3x", category="transaction_anomaly", reason="test", severity=SignalSeverity.HIGH, score_impact=25),
            RiskReason(signal_name="vel_rapid_txns_1h", category="velocity_network", reason="test", severity=SignalSeverity.LOW, score_impact=10),
        ]
        res = aggregator.aggregate(signals, 0, 3.0, 0)  # +1 ml -> 61
        assert res.score == 61
        assert res.level == RiskLevel.HIGH
        assert res.decision == RiskAction.HOLD_FOR_REVIEW

    def test_boundary_80_is_high(self):
        aggregator = RiskAggregator()
        from app.schemas import RiskReason, SignalSeverity
        signals = [
            RiskReason(signal_name="id_unverified_recipient", category="identity_trust", reason="test", severity=SignalSeverity.MEDIUM, score_impact=25),
            RiskReason(signal_name="txn_amount_spike_3x", category="transaction_anomaly", reason="test", severity=SignalSeverity.HIGH, score_impact=25),
            RiskReason(signal_name="beh_failed_attempts_spike", category="behavioral_anomaly", reason="test", severity=SignalSeverity.HIGH, score_impact=20),
            RiskReason(signal_name="vel_rapid_txns_1h", category="velocity_network", reason="test", severity=SignalSeverity.LOW, score_impact=10),
        ]
        res = aggregator.aggregate(signals, 0, 0, 0)
        assert res.score == 80
        assert res.level == RiskLevel.HIGH
        assert res.decision == RiskAction.HOLD_FOR_REVIEW

    def test_boundary_81_is_critical(self):
        aggregator = RiskAggregator()
        from app.schemas import RiskReason, SignalSeverity
        signals = [
            RiskReason(signal_name="id_unverified_recipient", category="identity_trust", reason="test", severity=SignalSeverity.MEDIUM, score_impact=25),
            RiskReason(signal_name="txn_amount_spike_3x", category="transaction_anomaly", reason="test", severity=SignalSeverity.HIGH, score_impact=25),
            RiskReason(signal_name="beh_failed_attempts_spike", category="behavioral_anomaly", reason="test", severity=SignalSeverity.HIGH, score_impact=20),
            RiskReason(signal_name="vel_rapid_txns_1h", category="velocity_network", reason="test", severity=SignalSeverity.LOW, score_impact=10),
        ]
        res = aggregator.aggregate(signals, 0, 3.0, 0)  # +1 ml -> 81
        assert res.score == 81
        assert res.level == RiskLevel.CRITICAL
        assert res.decision == RiskAction.BLOCK

    def test_score_capped_at_100(self):
        aggregator = RiskAggregator()
        from app.schemas import RiskReason, SignalSeverity
        signals = [
            RiskReason(signal_name="id_1", category="identity_trust", reason="test", severity=SignalSeverity.HIGH, score_impact=100),
            RiskReason(signal_name="txn_1", category="transaction_anomaly", reason="test", severity=SignalSeverity.HIGH, score_impact=100),
            RiskReason(signal_name="beh_1", category="behavioral_anomaly", reason="test", severity=SignalSeverity.HIGH, score_impact=100),
            RiskReason(signal_name="vel_1", category="velocity_network", reason="test", severity=SignalSeverity.HIGH, score_impact=100),
        ]
        res = aggregator.aggregate(signals, 0, 30.0, 50)
        assert res.score == 100
        assert res.level == RiskLevel.CRITICAL
        assert res.decision == RiskAction.BLOCK


class TestIsolationForest:
    def test_normal_transaction_low_score(self):
        from app.risk.engine import MLAnomalyDetector
        detector = MLAnomalyDetector()
        ctx = make_context()
        features = detector.extract_features(ctx)
        score = detector.predict(features)
        assert 0 <= score <= 30

    def test_extreme_outlier_high_score(self):
        from app.risk.engine import MLAnomalyDetector
        detector = MLAnomalyDetector()
        ctx = make_context(
            amount=1000000000, avg_amount=5000, median_amount=4000,
            is_new_recipient=True, txn_count_1h=50, txn_count_24h=100,
        )
        features = detector.extract_features(ctx)
        anomaly_score = detector.predict(features)
        assert anomaly_score > 0