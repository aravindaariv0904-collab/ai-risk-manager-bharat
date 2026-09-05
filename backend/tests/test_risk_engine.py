import pytest
from datetime import datetime
from app.risk.engine import (
    RuleEngine, TransactionContext, RiskAggregator,
    RiskLevel, RiskAction,
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
        assert "new_recipient_high_amount" in names
        score = next(r for r in reasons if r.signal_name == "new_recipient_high_amount")
        assert score.score_impact == 30

    def test_rapid_repeated_transactions(self):
        ctx = make_context(txn_count_1h=6)
        reasons = RuleEngine().evaluate(ctx)
        names = [r.signal_name for r in reasons]
        assert "rapid_repeated_txns" in names

    def test_rapid_below_threshold(self):
        ctx = make_context(txn_count_1h=5)
        reasons = RuleEngine().evaluate(ctx)
        names = [r.signal_name for r in reasons]
        assert "rapid_repeated_txns" not in names

    def test_unusual_time_late_night(self):
        ctx = make_context(hour=3)
        reasons = RuleEngine().evaluate(ctx)
        names = [r.signal_name for r in reasons]
        assert "unusual_time" in names

    def test_unusual_time_after_11pm(self):
        ctx = make_context(hour=23)
        reasons = RuleEngine().evaluate(ctx)
        names = [r.signal_name for r in reasons]
        assert "unusual_time" in names

    def test_unusual_time_normal_hours(self):
        ctx = make_context(hour=12)
        reasons = RuleEngine().evaluate(ctx)
        names = [r.signal_name for r in reasons]
        assert "unusual_time" not in names

    def test_failed_attempts(self):
        ctx = make_context(failed_count_24h=4)
        reasons = RuleEngine().evaluate(ctx)
        names = [r.signal_name for r in reasons]
        assert "multiple_failed_attempts" in names

    def test_amount_anomaly_above_p95(self):
        ctx = make_context(amount=20000, p95_amount=15000)
        reasons = RuleEngine().evaluate(ctx)
        names = [r.signal_name for r in reasons]
        assert "amount_anomaly" in names

    def test_amount_normal_below_p95(self):
        ctx = make_context(amount=12000, p95_amount=15000)
        reasons = RuleEngine().evaluate(ctx)
        names = [r.signal_name for r in reasons]
        assert "amount_anomaly" not in names

    def test_empty_history_no_rules(self):
        ctx = make_context(
            avg_amount=0, median_amount=0, p95_amount=0,
            txn_count_1h=0, txn_count_24h=0,
        )
        reasons = RuleEngine().evaluate(ctx)
        assert all(r.score_impact < 30 for r in reasons)


class TestRiskAggregator:
    def test_low_thresholds(self):
        aggregator = RiskAggregator()
        score, level, action, _ = aggregator.aggregate([], 0, 0, 0)
        assert score <= 30
        assert level == RiskLevel.LOW
        assert action == RiskAction.ALLOW

    def test_medium_thresholds(self):
        aggregator = RiskAggregator()
        score, level, action, _ = aggregator.aggregate([], 40, 0, 0)
        assert 31 <= score <= 65
        assert level == RiskLevel.MEDIUM
        assert action == RiskAction.VERIFY

    def test_high_thresholds(self):
        aggregator = RiskAggregator()
        score, level, action, _ = aggregator.aggregate([], 70, 0, 0)
        assert 66 <= score <= 100
        assert level == RiskLevel.HIGH
        assert action == RiskAction.WARN

    def test_boundary_30_is_low(self):
        aggregator = RiskAggregator()
        _, level, _, _ = aggregator.aggregate([], 30, 0, 0)
        assert level == RiskLevel.LOW

    def test_boundary_31_is_medium(self):
        aggregator = RiskAggregator()
        _, level, _, _ = aggregator.aggregate([], 31, 0, 0)
        assert level == RiskLevel.MEDIUM

    def test_boundary_65_is_medium(self):
        aggregator = RiskAggregator()
        _, level, _, _ = aggregator.aggregate([], 65, 0, 0)
        assert level == RiskLevel.MEDIUM

    def test_boundary_66_is_high(self):
        aggregator = RiskAggregator()
        _, level, _, _ = aggregator.aggregate([], 66, 0, 0)
        assert level == RiskLevel.HIGH

    def test_score_capped_at_100(self):
        aggregator = RiskAggregator()
        score, _, _, _ = aggregator.aggregate([], 100, 0, 0)
        assert score == 100

    def test_rule_score_contributes(self):
        from app.schemas import RiskReason, SignalSeverity
        aggregator = RiskAggregator()
        reasons = [
            RiskReason(signal_name="r1", reason="test", severity=SignalSeverity.HIGH, score_impact=30)
        ]
        score, _, _, _ = aggregator.aggregate(reasons, 10, 0, 0)
        assert score == 40


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