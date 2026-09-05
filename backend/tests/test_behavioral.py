import pytest
from datetime import datetime, timedelta
from app.risk.behavioral import BehavioralBaselineEngine, BehavioralProfile


class TestBehavioralBaselineEngine:
    @pytest.fixture
    def engine(self):
        return BehavioralBaselineEngine(window_days=90, min_baseline_txns=3)

    def test_new_user_insufficient_history(self, engine):
        payer_id = "user-new-001"
        history = []
        profile = engine.compute_profile_from_history(payer_id, history)

        assert profile.baseline_status == "INSUFFICIENT_HISTORY"
        assert profile.txn_count == 0
        assert profile.mean_amount == 0.0
        assert profile.median_amount == 0.0
        assert profile.p95_amount == 0.0
        assert profile.iqr_amount == 0.0
        assert profile.velocity_1h == 0
        assert profile.velocity_24h == 0
        assert profile.typical_hours == []

    def test_low_activity_user_insufficient_history(self, engine):
        payer_id = "user-low-002"
        now = datetime.utcnow()
        history = [
            {"amount": 50000, "created_at": (now - timedelta(days=2)).isoformat(), "merchant_id": "m1", "status": "CAPTURED"},
            {"amount": 75000, "created_at": (now - timedelta(days=10)).isoformat(), "merchant_id": "m2", "status": "CAPTURED"},
        ]
        profile = engine.compute_profile_from_history(payer_id, history, reference_time=now)

        assert profile.baseline_status == "INSUFFICIENT_HISTORY"
        assert profile.txn_count == 2
        assert profile.mean_amount == 62500.0
        assert profile.median_amount == 62500.0

    def test_established_baseline_robust_statistics(self, engine):
        payer_id = "user-est-003"
        ref_time = datetime(2026, 9, 5, 18, 0, 0)
        # Create history with known median, IQR, and typical hours (hour 10 and hour 14)
        history = [
            {"amount": 10000, "created_at": datetime(2026, 9, 1, 10, 15, 0).isoformat(), "merchant_id": "m1", "status": "CAPTURED"},
            {"amount": 20000, "created_at": datetime(2026, 9, 2, 10, 30, 0).isoformat(), "merchant_id": "m1", "status": "CAPTURED"},
            {"amount": 30000, "created_at": datetime(2026, 9, 3, 10, 45, 0).isoformat(), "merchant_id": "m2", "status": "CAPTURED"},
            {"amount": 40000, "created_at": datetime(2026, 9, 4, 14, 10, 0).isoformat(), "merchant_id": "m2", "status": "CAPTURED"},
            {"amount": 50000, "created_at": datetime(2026, 9, 4, 14, 20, 0).isoformat(), "merchant_id": "m3", "status": "CAPTURED"},
            {"amount": 100000, "created_at": datetime(2026, 9, 5, 14, 30, 0).isoformat(), "merchant_id": "m3", "status": "CAPTURED"},
        ]
        profile = engine.compute_profile_from_history(payer_id, history, reference_time=ref_time)

        assert profile.baseline_status == "ESTABLISHED"
        assert profile.txn_count == 6
        assert profile.min_amount == 10000.0
        assert profile.max_amount == 100000.0
        assert profile.median_amount == 35000.0
        assert profile.iqr_amount > 0
        assert 10 in profile.typical_hours or 14 in profile.typical_hours
        assert len(profile.top_merchants) >= 2

    def test_high_activity_user_velocity_calculation(self, engine):
        payer_id = "user-high-004"
        now = datetime.utcnow()
        # 10 transactions in last hour, 20 in last 24h
        history = [
            {"amount": 1000, "created_at": (now - timedelta(minutes=5 * i)).isoformat(), "merchant_id": "m1", "status": "CAPTURED"}
            for i in range(10)
        ] + [
            {"amount": 2000, "created_at": (now - timedelta(hours=3 + i)).isoformat(), "merchant_id": "m2", "status": "CAPTURED"}
            for i in range(10)
        ]
        profile = engine.compute_profile_from_history(payer_id, history, reference_time=now)

        assert profile.baseline_status == "ESTABLISHED"
        assert profile.txn_count == 20
        assert profile.velocity_1h == 10
        assert profile.velocity_24h == 20

    def test_failed_payment_ratio_metric(self, engine):
        payer_id = "user-failed-005"
        now = datetime.utcnow()
        history = [
            {"amount": 5000, "created_at": (now - timedelta(days=1)).isoformat(), "merchant_id": "m1", "status": "CAPTURED"},
            {"amount": 5000, "created_at": (now - timedelta(days=2)).isoformat(), "merchant_id": "m1", "status": "FAILED"},
            {"amount": 5000, "created_at": (now - timedelta(days=3)).isoformat(), "merchant_id": "m1", "status": "FAILED"},
            {"amount": 5000, "created_at": (now - timedelta(days=4)).isoformat(), "merchant_id": "m1", "status": "CAPTURED"},
        ]
        profile = engine.compute_profile_from_history(payer_id, history, reference_time=now)

        assert profile.baseline_status == "ESTABLISHED"
        assert profile.txn_count == 4
        assert profile.failed_ratio == 0.5  # 2 failed out of 4

    def test_missing_and_corrupt_fields_handled_gracefully(self, engine):
        payer_id = "user-corrupt-006"
        history = [
            {"amount": None, "created_at": "invalid_date_string"},
            {"amount": -500, "created_at": None},
            "not_a_dict_entry",
            None,
        ]
        profile = engine.compute_profile_from_history(payer_id, history)
        assert profile.baseline_status == "INSUFFICIENT_HISTORY"
        assert profile.txn_count == 0
