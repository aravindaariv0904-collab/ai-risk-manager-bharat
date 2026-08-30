from typing import List, Dict
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.models import RiskLevel, RiskAction, SignalSeverity
from app.schemas import RiskReason


@dataclass
class TransactionContext:
    amount: int
    currency: str
    merchant_id: str
    payer_id: str
    hour: int
    day_of_week: int
    is_new_recipient: bool
    txn_count_1h: int
    txn_count_24h: int
    txn_count_7d: int
    failed_count_24h: int
    avg_amount: float
    median_amount: float
    p95_amount: float
    frequent_merchants: List[str]
    typical_hours: List[int]


class RuleEngine:
    def __init__(self):
        self.rules = [
            ("new_recipient_high_amount", self._check_new_recipient_high_amount, 30),
            ("rapid_repeated_txns", self._check_rapid_repeated, 25),
            ("unusual_time", self._check_unusual_time, 15),
            ("multiple_failed_attempts", self._check_failed_attempts, 20),
            ("amount_anomaly", self._check_amount_anomaly, 20),
            ("high_amount_new_merchant", self._check_high_amount_new_merchant, 25),
        ]

    def evaluate(self, ctx: TransactionContext) -> List[RiskReason]:
        reasons = []
        for name, check_fn, max_score in self.rules:
            triggered, reason, score = check_fn(ctx)
            if triggered:
                reasons.append(RiskReason(
                    signal_name=name,
                    reason=reason,
                    severity=self._score_to_severity(score),
                    score_impact=score
                ))
        return reasons

    def _check_new_recipient_high_amount(self, ctx: TransactionContext):
        if ctx.is_new_recipient and ctx.amount > ctx.avg_amount * 3 and ctx.avg_amount > 0:
            return True, f"New recipient with amount ₹{ctx.amount/100:.0f} (avg: ₹{ctx.avg_amount/100:.0f})", 30
        return False, "", 0

    def _check_rapid_repeated(self, ctx: TransactionContext):
        if ctx.txn_count_1h > 5:
            return True, f"{ctx.txn_count_1h} transactions in the last hour", 25
        return False, "", 0

    def _check_unusual_time(self, ctx: TransactionContext):
        if ctx.hour < 6 or ctx.hour >= 23:
            return True, f"Transaction at unusual hour: {ctx.hour}:00", 15
        return False, "", 0

    def _check_failed_attempts(self, ctx: TransactionContext):
        if ctx.failed_count_24h > 3:
            return True, f"{ctx.failed_count_24h} failed transactions in last 24 hours", 20
        return False, "", 0

    def _check_amount_anomaly(self, ctx: TransactionContext):
        if ctx.amount > ctx.p95_amount and ctx.p95_amount > 0:
            return True, f"Amount ₹{ctx.amount/100:.0f} exceeds 95th percentile (₹{ctx.p95_amount/100:.0f})", 20
        return False, "", 0

    def _check_high_amount_new_merchant(self, ctx: TransactionContext):
        if ctx.is_new_recipient and ctx.amount > 500000:  # ₹5000
            return True, f"High amount ₹{ctx.amount/100:.0f} to new merchant", 25
        return False, "", 0

    def _score_to_severity(self, score: int) -> SignalSeverity:
        if score >= 25:
            return SignalSeverity.HIGH
        elif score >= 15:
            return SignalSeverity.MEDIUM
        return SignalSeverity.LOW


class BehavioralBaseline:
    def __init__(self):
        self._supabase = None

    @property
    def supabase(self):
        if self._supabase is None:
            from app.services.supabase_client import get_supabase_admin
            self._supabase = get_supabase_admin()
        return self._supabase

    async def get_context(self, payer_id: str, merchant_id: str, amount: int) -> TransactionContext:
        import numpy as np

        now = datetime.utcnow()
        hour = now.hour
        day_of_week = now.weekday()

        recent_txns = await self._get_recent_transactions(payer_id)
        merchant_txns = await self._get_merchant_transactions(payer_id, merchant_id)

        is_new_recipient = len(merchant_txns) == 0

        amounts = [txn["amount"] for txn in recent_txns]
        avg_amount = float(np.mean(amounts)) if amounts else 0
        median_amount = float(np.median(amounts)) if amounts else 0
        p95_amount = float(np.percentile(amounts, 95)) if amounts else 0

        txn_count_1h = len([t for t in recent_txns if (now - datetime.fromisoformat(t["created_at"].replace("Z", "+00:00"))).total_seconds() < 3600])
        txn_count_24h = len([t for t in recent_txns if (now - datetime.fromisoformat(t["created_at"].replace("Z", "+00:00"))).total_seconds() < 86400])
        txn_count_7d = len([t for t in recent_txns if (now - datetime.fromisoformat(t["created_at"].replace("Z", "+00:00"))).total_seconds() < 604800])

        failed_count_24h = len([t for t in recent_txns if t["status"] == "failed" and (now - datetime.fromisoformat(t["created_at"].replace("Z", "+00:00"))).total_seconds() < 86400])

        merchant_amounts = [t["amount"] for t in recent_txns]
        merchant_counts: Dict[str, int] = {}
        for t in recent_txns:
            mid = t.get("merchant_id")
            if mid:
                merchant_counts[mid] = merchant_counts.get(mid, 0) + 1
        frequent_merchants = sorted(merchant_counts, key=merchant_counts.get, reverse=True)[:5]

        hours = [datetime.fromisoformat(t["created_at"].replace("Z", "+00:00")).hour for t in recent_txns]
        hour_counts: Dict[int, int] = {}
        for h in hours:
            hour_counts[h] = hour_counts.get(h, 0) + 1
        typical_hours = sorted(hour_counts, key=hour_counts.get, reverse=True)[:3]

        return TransactionContext(
            amount=amount,
            currency="INR",
            merchant_id=merchant_id,
            payer_id=payer_id,
            hour=hour,
            day_of_week=day_of_week,
            is_new_recipient=is_new_recipient,
            txn_count_1h=txn_count_1h,
            txn_count_24h=txn_count_24h,
            txn_count_7d=txn_count_7d,
            failed_count_24h=failed_count_24h,
            avg_amount=avg_amount,
            median_amount=median_amount,
            p95_amount=p95_amount,
            frequent_merchants=frequent_merchants,
            typical_hours=typical_hours,
        )

    async def _get_recent_transactions(self, payer_id: str, days: int = 30) -> List[Dict]:
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        try:
            response = self.supabase.table("transactions").select("*").eq("payer_id", payer_id).gte("created_at", cutoff).order("created_at", desc=True).limit(100).execute()
            return response.data or []
        except Exception:
            return []

    async def _get_merchant_transactions(self, payer_id: str, merchant_id: str) -> List[Dict]:
        try:
            response = self.supabase.table("transactions").select("*").eq("payer_id", payer_id).eq("merchant_id", merchant_id).limit(10).execute()
            return response.data or []
        except Exception:
            return []


class MLAnomalyDetector:
    def __init__(self):
        import joblib
        import os

        self._joblib = joblib
        self._os = os
        self.model = None
        self.model_path = "models/isolation_forest.joblib"
        self._load_or_train()

    def _load_or_train(self):
        import numpy as np
        from sklearn.ensemble import IsolationForest
        import os

        # Try multiple paths for model persistence
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.model_path = os.path.join(base_dir, "models", "isolation_forest.joblib")

        if os.path.exists(self.model_path):
            try:
                self.model = self._joblib.load(self.model_path)
                return
            except Exception:
                pass
        self._train_initial_model()

    def _train_initial_model(self):
        import numpy as np
        from sklearn.ensemble import IsolationForest

        np.random.seed(42)
        n_normal = 1000
        normal_data = np.column_stack([
            np.random.lognormal(8, 1, n_normal),  # amount
            np.random.randint(6, 23, n_normal),    # hour
            np.random.randint(0, 7, n_normal),     # day_of_week
            np.random.randint(1, 5, n_normal),     # merchant_category (1-4)
            np.random.poisson(1, n_normal),        # txn_count_1h
            np.random.poisson(10, n_normal),       # txn_count_24h
            np.random.normal(0, 1, n_normal),      # amount_zscore
            np.random.randint(0, 2, n_normal),     # is_new_recipient
        ])

        self.model = IsolationForest(contamination=0.05, random_state=42, n_estimators=100)
        self.model.fit(normal_data)

        import os
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        self._joblib.dump(self.model, self.model_path)

    def predict(self, features) -> float:
        if self.model is None:
            return 0.0
        try:
            score = self.model.score_samples(features.reshape(1, -1))[0]
            normalized = max(0, min(1, (0.5 - score) / 0.5))
            return normalized * 30
        except Exception:
            return 0.0

    def extract_features(self, ctx: TransactionContext):
        import numpy as np

        amount_zscore = 0
        if ctx.median_amount > 0 and ctx.avg_amount > 0:
            amount_zscore = (ctx.amount - ctx.median_amount) / max(ctx.avg_amount * 0.5, 1)

        return np.array([
            ctx.amount,
            ctx.hour,
            ctx.day_of_week,
            1,
            ctx.txn_count_1h,
            ctx.txn_count_24h,
            amount_zscore,
            1 if ctx.is_new_recipient else 0,
        ])


class RiskAggregator:
    THRESHOLDS = {
        "LOW": (0, 30),
        "MEDIUM": (31, 65),
        "HIGH": (66, 100),
    }

    ACTIONS = {
        "LOW": RiskAction.ALLOW,
        "MEDIUM": RiskAction.VERIFY,
        "HIGH": RiskAction.WARN,
    }

    def aggregate(
        self,
        rule_reasons: List[RiskReason],
        behavior_score: int,
        ml_score: float,
        historical_risk: int = 0,
    ) -> tuple[int, RiskLevel, RiskAction, List[RiskReason]]:
        rule_score = sum(r.score_impact for r in rule_reasons)
        total_score = min(100, rule_score + behavior_score + int(ml_score) + historical_risk)

        if total_score <= 30:
            level = RiskLevel.LOW
        elif total_score <= 65:
            level = RiskLevel.MEDIUM
        else:
            level = RiskLevel.HIGH

        action = self.ACTIONS[level.value]

        return total_score, level, action, rule_reasons


class RiskEngine:
    def __init__(self):
        self.rule_engine = RuleEngine()
        self.baseline = BehavioralBaseline()
        self.ml_detector = MLAnomalyDetector()
        self.aggregator = RiskAggregator()

    async def evaluate(self, payer_id: str, merchant_id: str, amount: int) -> tuple[int, RiskLevel, RiskAction, List[RiskReason], Dict]:
        ctx = await self.baseline.get_context(payer_id, merchant_id, amount)

        rule_reasons = self.rule_engine.evaluate(ctx)

        behavior_score = self._calculate_behavior_score(ctx)

        features = self.ml_detector.extract_features(ctx)
        ml_score = self.ml_detector.predict(features)

        historical_risk = await self._get_historical_risk(payer_id)

        risk_score, risk_level, risk_action, reasons = self.aggregator.aggregate(
            rule_reasons, behavior_score, ml_score, historical_risk
        )

        details = {
            "rule_score": sum(r.score_impact for r in rule_reasons),
            "behavior_score": behavior_score,
            "ml_score": int(ml_score),
            "historical_risk": historical_risk,
            "context": {
                "amount": ctx.amount,
                "hour": ctx.hour,
                "is_new_recipient": ctx.is_new_recipient,
                "txn_count_1h": ctx.txn_count_1h,
                "txn_count_24h": ctx.txn_count_24h,
                "avg_amount": ctx.avg_amount,
            }
        }

        return risk_score, risk_level, risk_action, reasons, details

    def _calculate_behavior_score(self, ctx: TransactionContext) -> int:
        score = 0
        if ctx.txn_count_24h > 20:
            score += 10
        if ctx.is_new_recipient and ctx.amount > ctx.median_amount * 2:
            score += 15
        if ctx.hour not in ctx.typical_hours and ctx.typical_hours:
            score += 10
        return min(score, 30)

    async def _get_historical_risk(self, payer_id: str) -> int:
        """Compute average historical risk score for the payer from past risk decisions."""
        try:
            import numpy as np
            from app.services.supabase_client import get_supabase_admin

            supabase = get_supabase_admin()
            # Get the user's past transactions first
            txn_resp = supabase.table("transactions").select("id").eq("payer_id", payer_id).limit(20).execute()
            if not txn_resp.data:
                return 0

            txn_ids = [t["id"] for t in txn_resp.data]

            # Get risk decisions for those transactions
            decisions_resp = supabase.table("risk_decisions").select("score").in_("transaction_id", txn_ids).limit(20).execute()
            if decisions_resp.data:
                scores = [d["score"] for d in decisions_resp.data if d.get("score") is not None]
                if scores:
                    avg = float(np.mean(scores))
                    # Historical risk adds up to 10 points if average was high
                    return min(10, int(avg * 0.1))
        except Exception:
            pass
        return 0


risk_engine = RiskEngine()