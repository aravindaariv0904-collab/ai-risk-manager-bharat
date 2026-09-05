from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import os
import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
import structlog

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Canonical Feature Schema Definition
# ---------------------------------------------------------------------------
CANONICAL_FEATURE_NAMES: List[str] = [
    "amount_inr",              # Transaction amount in Indian Rupees (float >= 0)
    "hour",                    # Hour of day (0 to 23)
    "day_of_week",             # Day of week (0 to 6)
    "is_new_recipient",        # 1.0 if new/unverified recipient, else 0.0
    "txn_count_1h",            # Velocity in past 1 hour (>= 0)
    "txn_count_24h",           # Velocity in past 24 hours (>= 0)
    "failed_count_24h",        # Failed attempts in past 24 hours (>= 0)
    "amount_ratio_to_avg",     # Ratio of amount to user average (>= 0)
    "is_unusual_hour",         # 1.0 if outside typical user hours or late night, else 0.0
    "merchant_category_code",  # Numeric category code (0=unknown, 1=retail, 2=food, 3=services, 4=electronics)
]

CANONICAL_MODEL_VERSION: str = "v1.1-isolation-forest"

CATEGORY_MAP: Dict[str, float] = {
    "grocery": 1.0,
    "retail": 1.0,
    "general": 1.0,
    "store": 1.0,
    "food": 2.0,
    "restaurant": 2.0,
    "dining": 2.0,
    "tea": 2.0,
    "services": 3.0,
    "tailoring": 3.0,
    "utility": 3.0,
    "repair": 3.0,
    "electronics": 4.0,
    "luxury": 4.0,
    "jewellery": 4.0,
}


class CanonicalFeaturePipeline:
    """
    Unified, canonical feature extraction pipeline.
    Guarantees 100% consistency between model training and model inference.
    """

    @classmethod
    def get_feature_names(cls) -> List[str]:
        return list(CANONICAL_FEATURE_NAMES)

    @classmethod
    def get_feature_count(cls) -> int:
        return len(CANONICAL_FEATURE_NAMES)

    @classmethod
    def extract_features(cls, ctx: Any) -> np.ndarray:
        """
        Extract the 1D canonical feature vector from a TransactionContext or dictionary.
        Safely handles missing, invalid, or NaN values.
        """
        # 1. Amount in INR (ctx.amount is in paise: 100 paise = 1 INR)
        raw_amount = getattr(ctx, "amount", None)
        if raw_amount is None and isinstance(ctx, dict):
            raw_amount = ctx.get("amount")
        try:
            amount_inr = max(0.0, float(raw_amount or 0.0) / 100.0)
        except (ValueError, TypeError):
            amount_inr = 0.0

        # 2. Hour
        raw_hour = getattr(ctx, "hour", None)
        if raw_hour is None and isinstance(ctx, dict):
            raw_hour = ctx.get("hour")
        try:
            hour = float(raw_hour if raw_hour is not None else 12.0) % 24.0
        except (ValueError, TypeError):
            hour = 12.0

        # 3. Day of week
        raw_dow = getattr(ctx, "day_of_week", None)
        if raw_dow is None and isinstance(ctx, dict):
            raw_dow = ctx.get("day_of_week")
        try:
            day_of_week = float(raw_dow if raw_dow is not None else 0.0) % 7.0
        except (ValueError, TypeError):
            day_of_week = 0.0

        # 4. Is new recipient
        is_new = getattr(ctx, "is_new_recipient", None)
        if is_new is None and isinstance(ctx, dict):
            is_new = ctx.get("is_new_recipient")
        is_new_recipient = 1.0 if bool(is_new) else 0.0

        # 5. Transaction velocity 1 hour
        raw_v1h = getattr(ctx, "txn_count_1h", None)
        if raw_v1h is None and isinstance(ctx, dict):
            raw_v1h = ctx.get("txn_count_1h")
        try:
            txn_count_1h = max(0.0, float(raw_v1h or 0.0))
        except (ValueError, TypeError):
            txn_count_1h = 0.0

        # 6. Transaction velocity 24 hours
        raw_v24h = getattr(ctx, "txn_count_24h", None)
        if raw_v24h is None and isinstance(ctx, dict):
            raw_v24h = ctx.get("txn_count_24h")
        try:
            txn_count_24h = max(0.0, float(raw_v24h or 0.0))
        except (ValueError, TypeError):
            txn_count_24h = 0.0

        # 7. Failed attempts 24 hours
        raw_fail = getattr(ctx, "failed_count_24h", None)
        if raw_fail is None and isinstance(ctx, dict):
            raw_fail = ctx.get("failed_count_24h")
        try:
            failed_count_24h = max(0.0, float(raw_fail or 0.0))
        except (ValueError, TypeError):
            failed_count_24h = 0.0

        # 8. Amount ratio to average
        raw_avg = getattr(ctx, "avg_amount", None)
        if raw_avg is None and isinstance(ctx, dict):
            raw_avg = ctx.get("avg_amount")
        try:
            avg_inr = (float(raw_avg or 0.0) / 100.0) if raw_avg else 0.0
            if avg_inr > 0.0:
                amount_ratio_to_avg = min(50.0, max(0.0, amount_inr / avg_inr))
            else:
                amount_ratio_to_avg = 1.0
        except (ValueError, TypeError, ZeroDivisionError):
            amount_ratio_to_avg = 1.0

        # 9. Is unusual hour
        typical_hours = getattr(ctx, "typical_hours", None)
        if typical_hours is None and isinstance(ctx, dict):
            typical_hours = ctx.get("typical_hours")
        if typical_hours and isinstance(typical_hours, (list, set, tuple)):
            is_unusual_hour = 1.0 if int(hour) not in typical_hours else 0.0
        else:
            is_unusual_hour = 1.0 if (hour < 6.0 or hour >= 23.0) else 0.0

        # 10. Merchant category code
        cat = getattr(ctx, "merchant_category", None)
        if cat is None and isinstance(ctx, dict):
            cat = ctx.get("merchant_category")
        merchant_category_code = 0.0
        if cat and isinstance(cat, str):
            merchant_category_code = CATEGORY_MAP.get(cat.lower().strip(), 0.0)

        feature_vector = np.array([
            amount_inr,
            hour,
            day_of_week,
            is_new_recipient,
            txn_count_1h,
            txn_count_24h,
            failed_count_24h,
            amount_ratio_to_avg,
            is_unusual_hour,
            merchant_category_code,
        ], dtype=np.float64)

        # Impute any possible NaN or infinite values safely
        return np.nan_to_num(feature_vector, nan=0.0, posinf=100.0, neginf=-100.0)

    @classmethod
    def generate_training_data(cls, n_samples: int = 2500, seed: int = 42) -> np.ndarray:
        """
        Generate synthetic training dataset matching the canonical feature distribution.
        """
        np.random.seed(seed)

        amount_inr = np.clip(np.random.lognormal(mean=6.5, sigma=1.2, size=n_samples), 1.0, 50000.0)
        hour = np.random.randint(6, 23, size=n_samples).astype(np.float64)
        day_of_week = np.random.randint(0, 7, size=n_samples).astype(np.float64)
        is_new_recipient = np.random.binomial(n=1, p=0.20, size=n_samples).astype(np.float64)
        txn_count_1h = np.random.poisson(lam=0.4, size=n_samples).astype(np.float64)
        txn_count_24h = np.random.poisson(lam=4.0, size=n_samples).astype(np.float64)
        failed_count_24h = np.random.poisson(lam=0.05, size=n_samples).astype(np.float64)
        amount_ratio_to_avg = np.clip(np.random.normal(loc=1.0, scale=0.4, size=n_samples), 0.1, 10.0)
        is_unusual_hour = np.random.binomial(n=1, p=0.08, size=n_samples).astype(np.float64)
        merchant_category_code = np.random.randint(0, 5, size=n_samples).astype(np.float64)

        data = np.column_stack([
            amount_inr,
            hour,
            day_of_week,
            is_new_recipient,
            txn_count_1h,
            txn_count_24h,
            failed_count_24h,
            amount_ratio_to_avg,
            is_unusual_hour,
            merchant_category_code,
        ])
        return data


class MLAnomalyDetector:
    """
    Isolation Forest anomaly detection engine for payment risk scoring.
    
    IMPORTANT: This model calculates an anomaly / risk contribution score (0 to 30 points)
    reflecting deviations from baseline transaction behavior. It does NOT predict the
    absolute probability of fraud.
    """

    def __init__(self, model_path: Optional[str] = None):
        self.pipeline = CanonicalFeaturePipeline()
        self.model: Optional[IsolationForest] = None
        self.metadata: Dict[str, Any] = {}

        if model_path:
            self.model_path = model_path
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.model_path = os.path.join(base_dir, "models", "isolation_forest.joblib")

        self._load_or_train()

    def _load_or_train(self) -> None:
        """
        Load model bundle and validate schema compatibility.
        If missing, incompatible, or invalid, trains a fresh model with canonical schema.
        """
        if os.path.exists(self.model_path):
            try:
                bundle = joblib.load(self.model_path)
                if self._validate_bundle(bundle):
                    self.model = bundle["model"]
                    self.metadata = bundle["metadata"]
                    logger.info("Loaded validated Isolation Forest model bundle", version=self.metadata.get("model_version"))
                    return
                else:
                    logger.warning("Existing model bundle failed schema validation. Retraining...")
            except Exception as e:
                logger.warning("Failed to load model file, retraining", error=str(e))

        self.train_and_save()

    def _validate_bundle(self, bundle: Any) -> bool:
        """Validate that the persisted bundle contains valid model and exact feature schema."""
        if not isinstance(bundle, dict):
            return False
        if "model" not in bundle or "metadata" not in bundle:
            return False

        meta = bundle["metadata"]
        expected_features = self.pipeline.get_feature_names()
        if meta.get("feature_names") != expected_features:
            return False
        if meta.get("feature_count") != len(expected_features):
            return False

        model = bundle["model"]
        if not hasattr(model, "score_samples"):
            return False

        return True

    def train_and_save(self) -> None:
        """Train Isolation Forest on canonical training dataset and persist bundle."""
        training_data = self.pipeline.generate_training_data(n_samples=2500, seed=42)

        model = IsolationForest(
            contamination=0.05,
            random_state=42,
            n_estimators=100,
            max_samples="auto",
        )
        model.fit(training_data)

        self.metadata = {
            "model_version": CANONICAL_MODEL_VERSION,
            "feature_names": self.pipeline.get_feature_names(),
            "feature_count": self.pipeline.get_feature_count(),
            "trained_at": datetime.utcnow().isoformat(),
            "contamination": 0.05,
            "algorithm": "IsolationForest",
            "n_samples": len(training_data),
        }

        bundle = {
            "model": model,
            "metadata": self.metadata,
        }

        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        joblib.dump(bundle, self.model_path)
        self.model = model
        logger.info("Successfully trained and persisted canonical Isolation Forest model", path=self.model_path)

    def extract_features(self, ctx: Any) -> np.ndarray:
        """Extract canonical feature vector from transaction context."""
        return self.pipeline.extract_features(ctx)

    def predict(self, features: Union[np.ndarray, List[float]]) -> float:
        """
        Compute transaction anomaly / risk contribution score (0.0 to 30.0 points).
        Validates feature vector dimensions before prediction.
        """
        if self.model is None:
            return 0.0

        if isinstance(features, list):
            features = np.array(features, dtype=np.float64)

        if not isinstance(features, np.ndarray):
            raise TypeError(f"Expected features as np.ndarray or list, got {type(features)}")

        # Validate feature dimensions
        expected_dim = self.pipeline.get_feature_count()
        if features.ndim == 1:
            if features.shape[0] != expected_dim:
                raise ValueError(f"Feature dimension mismatch: expected {expected_dim}, got {features.shape[0]}")
            features_2d = features.reshape(1, -1)
        elif features.ndim == 2:
            if features.shape[1] != expected_dim:
                raise ValueError(f"Feature dimension mismatch: expected (*, {expected_dim}), got {features.shape}")
            features_2d = features
        else:
            raise ValueError(f"Invalid feature array dimensions: {features.ndim}D (expected 1D or 2D)")

        try:
            # score_samples returns negative anomaly score: higher = normal, lower = anomalous (around -0.5 to 0.5)
            raw_score = self.model.score_samples(features_2d)[0]
            # Normalize to 0.0 (normal) to 1.0 (anomalous)
            normalized_anomaly = max(0.0, min(1.0, (0.5 - raw_score) / 0.5))
            # Return risk contribution (0 to 30 points)
            return round(normalized_anomaly * 30.0, 2)
        except Exception as e:
            logger.warning("Anomaly scoring failed, returning 0.0", error=str(e))
            return 0.0
