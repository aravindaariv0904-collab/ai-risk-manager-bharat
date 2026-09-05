import pytest
import numpy as np
import tempfile
import os
import joblib
from sklearn.ensemble import IsolationForest

from app.risk.ml_pipeline import (
    CanonicalFeaturePipeline,
    MLAnomalyDetector,
    CANONICAL_FEATURE_NAMES,
    CANONICAL_MODEL_VERSION,
)
from app.risk.engine import TransactionContext


def make_context(**overrides) -> TransactionContext:
    defaults = dict(
        amount=25000,  # 25000 paise = 250 INR
        currency="INR",
        merchant_id="m_123",
        payer_id="u_456",
        hour=14,
        day_of_week=2,
        is_new_recipient=False,
        is_unverified_merchant=False,
        txn_count_1h=1,
        txn_count_24h=4,
        txn_count_7d=15,
        failed_count_24h=0,
        avg_amount=30000,
        median_amount=25000,
        p95_amount=60000,
        frequent_merchants=["m_123"],
        typical_hours=[12, 13, 14, 15],
        merchant_category="grocery",
    )
    defaults.update(overrides)
    return TransactionContext(**defaults)


class TestCanonicalFeaturePipeline:
    def test_feature_names_ordering(self):
        names = CanonicalFeaturePipeline.get_feature_names()
        assert names == [
            "amount_inr",
            "hour",
            "day_of_week",
            "is_new_recipient",
            "txn_count_1h",
            "txn_count_24h",
            "failed_count_24h",
            "amount_ratio_to_avg",
            "is_unusual_hour",
            "merchant_category_code",
        ]
        assert CanonicalFeaturePipeline.get_feature_count() == 10

    def test_feature_extraction_shape_and_types(self):
        ctx = make_context()
        features = CanonicalFeaturePipeline.extract_features(ctx)
        assert isinstance(features, np.ndarray)
        assert features.shape == (10,)
        assert features.dtype == np.float64
        assert not np.isnan(features).any()
        assert not np.isinf(features).any()

    def test_feature_values_accuracy(self):
        ctx = make_context(
            amount=50000,  # ₹500
            hour=16,
            day_of_week=4,
            is_new_recipient=True,
            txn_count_1h=2,
            txn_count_24h=8,
            failed_count_24h=1,
            avg_amount=25000,  # ₹250 -> ratio = 2.0
            typical_hours=[10, 11, 12],  # hour 16 is unusual -> 1.0
            merchant_category="restaurant",  # food = 2.0
        )
        features = CanonicalFeaturePipeline.extract_features(ctx)
        expected = np.array([500.0, 16.0, 4.0, 1.0, 2.0, 8.0, 1.0, 2.0, 1.0, 2.0])
        np.testing.assert_allclose(features, expected, rtol=1e-5)

    def test_training_and_inference_feature_compatibility(self):
        training_data = CanonicalFeaturePipeline.generate_training_data(n_samples=500, seed=42)
        assert training_data.shape == (500, 10)
        assert not np.isnan(training_data).any()

        # Extract inference feature vector
        ctx = make_context()
        inference_vector = CanonicalFeaturePipeline.extract_features(ctx)

        # Ensure shapes and dimension counts match perfectly
        assert training_data.shape[1] == len(inference_vector)

    def test_missing_and_invalid_attributes_handling(self):
        # All fields set to None / zero
        bad_ctx = {
            "amount": None,
            "hour": None,
            "day_of_week": None,
            "is_new_recipient": None,
            "txn_count_1h": None,
            "txn_count_24h": None,
            "failed_count_24h": None,
            "avg_amount": 0,
            "typical_hours": None,
            "merchant_category": None,
        }
        features = CanonicalFeaturePipeline.extract_features(bad_ctx)
        assert features.shape == (10,)
        assert not np.isnan(features).any()
        assert features[0] == 0.0  # amount_inr defaults to 0.0
        assert features[7] == 1.0  # ratio defaults to 1.0 when avg is 0


class TestMLAnomalyDetector:
    def test_model_bundle_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = os.path.join(tmpdir, "test_iso.joblib")
            detector = MLAnomalyDetector(model_path=model_path)

            assert os.path.exists(model_path)
            bundle = joblib.load(model_path)
            assert "model" in bundle
            assert "metadata" in bundle
            meta = bundle["metadata"]
            assert meta["model_version"] == CANONICAL_MODEL_VERSION
            assert meta["feature_names"] == CANONICAL_FEATURE_NAMES
            assert meta["feature_count"] == 10
            assert "trained_at" in meta

    def test_anomaly_score_bounds_and_terminology(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = os.path.join(tmpdir, "test_iso.joblib")
            detector = MLAnomalyDetector(model_path=model_path)

            ctx = make_context()
            features = detector.extract_features(ctx)
            anomaly_contribution = detector.predict(features)

            # Returns risk contribution points, bounded [0.0, 30.0]
            assert 0.0 <= anomaly_contribution <= 30.0
            assert isinstance(anomaly_contribution, float)

    def test_dimension_mismatch_rejection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = os.path.join(tmpdir, "test_iso.joblib")
            detector = MLAnomalyDetector(model_path=model_path)

            # Pass 8 features instead of 10
            wrong_dim_features = np.zeros(8)
            with pytest.raises(ValueError, match="Feature dimension mismatch"):
                detector.predict(wrong_dim_features)

            # Pass 2D with wrong column count
            wrong_2d = np.zeros((1, 5))
            with pytest.raises(ValueError, match="Feature dimension mismatch"):
                detector.predict(wrong_2d)

    def test_incompatible_bundle_rejection_and_retraining(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = os.path.join(tmpdir, "corrupt_iso.joblib")
            # Save an incompatible legacy bundle
            fake_bundle = {
                "model": IsolationForest().fit(np.zeros((10, 4))),
                "metadata": {
                    "feature_names": ["old_feat_1", "old_feat_2"],
                    "feature_count": 2,
                }
            }
            joblib.dump(fake_bundle, model_path)

            # Instantiating detector should detect schema incompatibility, reject it, and retrain cleanly
            detector = MLAnomalyDetector(model_path=model_path)
            assert detector.metadata["feature_count"] == 10
            assert detector.metadata["feature_names"] == CANONICAL_FEATURE_NAMES
            assert detector.predict(np.zeros(10)) >= 0.0
