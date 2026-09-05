from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import math

from app.models import RiskLevel, RiskAction, SignalSeverity
from app.schemas import RiskReason, CategoryScores, CompositeRiskOutput
from app.risk.ml_pipeline import (
    MLAnomalyDetector,
    CanonicalFeaturePipeline,
    CANONICAL_FEATURE_NAMES,
    CANONICAL_MODEL_VERSION,
)

# ---------------------------------------------------------------------------
# Signal Category Constants & Caps
# ---------------------------------------------------------------------------
CATEGORY_IDENTITY_TRUST = "identity_trust"
CATEGORY_TRANSACTION_ANOMALY = "transaction_anomaly"
CATEGORY_BEHAVIORAL_ANOMALY = "behavioral_anomaly"
CATEGORY_VELOCITY_NETWORK = "velocity_network"
CATEGORY_ML_ANOMALY = "ml_anomaly"

CATEGORY_MAX_SCORES = {
    CATEGORY_IDENTITY_TRUST: 25,
    CATEGORY_TRANSACTION_ANOMALY: 25,
    CATEGORY_BEHAVIORAL_ANOMALY: 25,
    CATEGORY_VELOCITY_NETWORK: 15,
    CATEGORY_ML_ANOMALY: 10,
}

TOTAL_MAX_SCORE = sum(CATEGORY_MAX_SCORES.values())  # 100


# ---------------------------------------------------------------------------
# Transaction Context
# ---------------------------------------------------------------------------
@dataclass
class TransactionContext:
    amount: int
    currency: str
    merchant_id: str
    payer_id: str
    hour: int
    day_of_week: int
    is_new_recipient: bool
    is_unverified_merchant: bool
    txn_count_1h: int
    txn_count_24h: int
    txn_count_7d: int
    failed_count_24h: int
    avg_amount: float
    median_amount: float
    p95_amount: float
    frequent_merchants: List[str]
    typical_hours: List[int]
    merchant_category: Optional[str] = None
    merchant_category_history: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Composite Risk Evaluation Result
# ---------------------------------------------------------------------------
class CompositeRiskResult:
    """
    Composite risk evaluation output containing the final score (0-100),
    risk level, decision, signals, category breakdown, and explanation context.
    Supports unpacking as a tuple for flexible integration.
    """
    def __init__(
        self,
        score: int,
        level: RiskLevel,
        decision: RiskAction,
        signals: List[RiskReason],
        category_scores: CategoryScores,
        explanation_data: Dict,
    ):
        self.score = score
        self.level = level
        self.decision = decision
        self.action = decision  # alias for backward compat
        self.signals = signals
        self.reasons = signals   # alias for backward compat
        self.category_scores = category_scores
        self.explanation_data = explanation_data

    def __iter__(self):
        yield self.score
        yield self.level
        yield self.decision
        yield self.signals
        yield self.category_scores
        yield self.explanation_data

    def to_dict(self) -> Dict:
        return {
            "score": self.score,
            "level": self.level.value if hasattr(self.level, "value") else str(self.level),
            "decision": self.decision.value if hasattr(self.decision, "value") else str(self.decision),
            "signals": [s.model_dump() if hasattr(s, "model_dump") else s for s in self.signals],
            "category_scores": self.category_scores.model_dump() if hasattr(self.category_scores, "model_dump") else self.category_scores,
            "explanation_data": self.explanation_data,
        }

    def to_schema(self) -> CompositeRiskOutput:
        return CompositeRiskOutput(
            score=self.score,
            level=self.level,
            decision=self.decision,
            signals=self.signals,
            category_scores=self.category_scores,
            explanation_data=self.explanation_data,
        )


# ---------------------------------------------------------------------------
# Rule Engine
# ---------------------------------------------------------------------------
class RuleEngine:
    """
    Evaluates multi-category deterministic risk signals with canonical signal IDs.
    Each signal is assigned to a bounded risk category.
    """
    def __init__(self):
        self.rules = [
            # Identity / Trust signals (Category: identity_trust)
            ("id_new_recipient", CATEGORY_IDENTITY_TRUST, self._check_new_recipient, 10),
            ("id_unverified_recipient", CATEGORY_IDENTITY_TRUST, self._check_unverified_merchant, 15),

            # Transaction Anomaly signals (Category: transaction_anomaly)
            ("txn_amount_spike_3x", CATEGORY_TRANSACTION_ANOMALY, self._check_amount_spike_3x, 20),
            ("txn_amount_exceeds_p95", CATEGORY_TRANSACTION_ANOMALY, self._check_amount_exceeds_p95, 15),
            ("txn_high_amount_new_recipient", CATEGORY_TRANSACTION_ANOMALY, self._check_high_amount_new_recipient, 20),

            # Behavioral Anomaly signals (Category: behavioral_anomaly)
            ("beh_unusual_hour", CATEGORY_BEHAVIORAL_ANOMALY, self._check_unusual_hour, 15),
            ("beh_failed_attempts_spike", CATEGORY_BEHAVIORAL_ANOMALY, self._check_failed_attempts, 20),
            ("beh_unusual_category", CATEGORY_BEHAVIORAL_ANOMALY, self._check_unusual_category, 10),

            # Velocity / Network signals (Category: velocity_network)
            ("vel_rapid_txns_1h", CATEGORY_VELOCITY_NETWORK, self._check_rapid_1h, 10),
            ("vel_excessive_txns_24h", CATEGORY_VELOCITY_NETWORK, self._check_excessive_24h, 10),
        ]

    def evaluate(self, ctx: TransactionContext) -> List[RiskReason]:
        reasons = []
        for name, category, check_fn, default_score in self.rules:
            triggered, reason_msg, score = check_fn(ctx)
            if triggered:
                reasons.append(RiskReason(
                    signal_name=name,
                    category=category,
                    reason=reason_msg,
                    severity=self._score_to_severity(score),
                    score_impact=score,
                ))
        return reasons

    # --- Category: Identity / Trust ---
    def _check_new_recipient(self, ctx: TransactionContext) -> Tuple[bool, str, int]:
        if ctx.is_new_recipient:
            return True, "First-time transfer to this recipient / contact.", 10
        return False, "", 0

    def _check_unverified_merchant(self, ctx: TransactionContext) -> Tuple[bool, str, int]:
        if ctx.is_unverified_merchant:
            return True, "Recipient or merchant is not verified on the network.", 15
        return False, "", 0

    # --- Category: Transaction Anomaly ---
    def _check_amount_spike_3x(self, ctx: TransactionContext) -> Tuple[bool, str, int]:
        if ctx.avg_amount > 0 and ctx.amount > ctx.avg_amount * 3:
            return True, f"Transaction amount ₹{ctx.amount/100:.0f} is >3x higher than user average (₹{ctx.avg_amount/100:.0f})", 20
        return False, "", 0

    def _check_amount_exceeds_p95(self, ctx: TransactionContext) -> Tuple[bool, str, int]:
        if ctx.p95_amount > 0 and ctx.amount > ctx.p95_amount:
            return True, f"Transaction amount ₹{ctx.amount/100:.0f} exceeds 95th percentile baseline (₹{ctx.p95_amount/100:.0f})", 15
        return False, "", 0

    def _check_high_amount_new_recipient(self, ctx: TransactionContext) -> Tuple[bool, str, int]:
        if ctx.is_new_recipient and ctx.amount > 500000:  # > ₹5,000
            return True, f"High amount transfer ₹{ctx.amount/100:.0f} to an unestablished recipient", 20
        return False, "", 0

    # --- Category: Behavioral Anomaly ---
    def _check_unusual_hour(self, ctx: TransactionContext) -> Tuple[bool, str, int]:
        is_odd_hour = ctx.hour < 6 or ctx.hour >= 23
        is_outside_typical = bool(ctx.typical_hours and ctx.hour not in ctx.typical_hours)
        if is_odd_hour or is_outside_typical:
            detail = f"{ctx.hour:02d}:00"
            return True, f"Transaction attempted at unusual hour: {detail}", 15
        return False, "", 0

    def _check_failed_attempts(self, ctx: TransactionContext) -> Tuple[bool, str, int]:
        if ctx.failed_count_24h > 3:
            return True, f"{ctx.failed_count_24h} failed transactions in last 24 hours (high failure frequency)", 20
        return False, "", 0

    def _check_unusual_category(self, ctx: TransactionContext) -> Tuple[bool, str, int]:
        if (
            ctx.merchant_category
            and ctx.merchant_category_history
            and ctx.merchant_category not in ctx.merchant_category_history
            and ctx.txn_count_7d > 5
        ):
            return True, f"Uncharacteristic merchant category '{ctx.merchant_category}' for this payer", 10
        return False, "", 0

    # --- Category: Velocity / Network ---
    def _check_rapid_1h(self, ctx: TransactionContext) -> Tuple[bool, str, int]:
        if ctx.txn_count_1h > 5:
            return True, f"Elevated 1-hour velocity: {ctx.txn_count_1h} transactions in last 60 minutes", 10
        return False, "", 0

    def _check_excessive_24h(self, ctx: TransactionContext) -> Tuple[bool, str, int]:
        if ctx.txn_count_24h > 20:
            return True, f"Abnormal daily frequency: {ctx.txn_count_24h} transactions in last 24 hours", 10
        return False, "", 0

    def _score_to_severity(self, score: int) -> SignalSeverity:
        if score >= 20:
            return SignalSeverity.HIGH
        elif score >= 12:
            return SignalSeverity.MEDIUM
        return SignalSeverity.LOW


# ---------------------------------------------------------------------------
# Behavioral Baseline Context Retriever
# ---------------------------------------------------------------------------
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

        # Check if merchant is verified and get category
        is_unverified = False
        merchant_category = None
        try:
            m_resp = self.supabase.table("merchants").select("*").eq("id", merchant_id).maybe_single().execute()
            if m_resp.data:
                merchant_category = m_resp.data.get("business_category")
                profile = m_resp.data.get("risk_profile") or {}
                if isinstance(profile, dict) and profile.get("is_verified") is False:
                    is_unverified = True
        except Exception:
            pass

        amounts = [txn["amount"] for txn in recent_txns if txn.get("amount") is not None]
        avg_amount = float(np.mean(amounts)) if amounts else 0.0
        median_amount = float(np.median(amounts)) if amounts else 0.0
        p95_amount = float(np.percentile(amounts, 95)) if amounts else 0.0

        def parse_dt(val):
            if isinstance(val, datetime):
                return val.replace(tzinfo=None) if val.tzinfo else val
            if isinstance(val, str):
                try:
                    return datetime.fromisoformat(val.replace("Z", "+00:00")).replace(tzinfo=None)
                except Exception:
                    pass
            return datetime.utcnow()

        txn_count_1h = len([t for t in recent_txns if (now - parse_dt(t.get("created_at"))).total_seconds() < 3600])
        txn_count_24h = len([t for t in recent_txns if (now - parse_dt(t.get("created_at"))).total_seconds() < 86400])
        txn_count_7d = len([t for t in recent_txns if (now - parse_dt(t.get("created_at"))).total_seconds() < 604800])

        failed_count_24h = len([
            t for t in recent_txns
            if t.get("status") == "failed" and (now - parse_dt(t.get("created_at"))).total_seconds() < 86400
        ])

        merchant_counts: Dict[str, int] = {}
        for t in recent_txns:
            mid = t.get("merchant_id")
            if mid:
                merchant_counts[mid] = merchant_counts.get(mid, 0) + 1
        frequent_merchants = sorted(merchant_counts, key=merchant_counts.get, reverse=True)[:5]

        hours = [parse_dt(t.get("created_at")).hour for t in recent_txns]
        hour_counts: Dict[int, int] = {}
        for h in hours:
            hour_counts[h] = hour_counts.get(h, 0) + 1
        typical_hours = sorted(hour_counts, key=hour_counts.get, reverse=True)[:3]

        merchant_category_history = []
        for t in recent_txns:
            cat = t.get("merchant_category") or t.get("category")
            if cat and cat not in merchant_category_history:
                merchant_category_history.append(cat)

        return TransactionContext(
            amount=amount,
            currency="INR",
            merchant_id=merchant_id,
            payer_id=payer_id,
            hour=hour,
            day_of_week=day_of_week,
            is_new_recipient=is_new_recipient,
            is_unverified_merchant=is_unverified,
            txn_count_1h=txn_count_1h,
            txn_count_24h=txn_count_24h,
            txn_count_7d=txn_count_7d,
            failed_count_24h=failed_count_24h,
            avg_amount=avg_amount,
            median_amount=median_amount,
            p95_amount=p95_amount,
            frequent_merchants=frequent_merchants,
            typical_hours=typical_hours,
            merchant_category=merchant_category,
            merchant_category_history=merchant_category_history,
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


# ---------------------------------------------------------------------------
# Composite Risk Aggregator
# ---------------------------------------------------------------------------
class RiskAggregator:
    """
    Defensible 0-100 Composite Risk Aggregator with Independent Dimensions
    and Anti-Stacking controls.

    Dimension Allocations:
      - Identity / Trust:       0 to 25
      - Transaction Anomaly:    0 to 25
      - Behavioral Anomaly:     0 to 25
      - Velocity / Network:     0 to 15
      - ML Anomaly:             0 to 10
      Total Maximum = 100

    Thresholds:
      - 0  to 30:  LOW      -> ALLOW
      - 31 to 60:  MEDIUM   -> STEP_UP_VERIFICATION
      - 61 to 80:  HIGH     -> HOLD_FOR_REVIEW
      - 81 to 100: CRITICAL -> BLOCK
    """

    THRESHOLDS = {
        "LOW": (0, 30),
        "MEDIUM": (31, 60),
        "HIGH": (61, 80),
        "CRITICAL": (81, 100),
    }

    ACTIONS = {
        RiskLevel.LOW: RiskAction.ALLOW,
        RiskLevel.MEDIUM: RiskAction.STEP_UP_VERIFICATION,
        RiskLevel.HIGH: RiskAction.HOLD_FOR_REVIEW,
        RiskLevel.CRITICAL: RiskAction.BLOCK,
    }

    def aggregate(
        self,
        rule_reasons: List[RiskReason],
        behavior_score: int = 0,
        ml_score: float = 0.0,
        historical_risk: int = 0,
        context_summary: Optional[Dict] = None,
    ) -> CompositeRiskResult:
        all_signals: List[RiskReason] = list(rule_reasons)

        # 1. Identity / Trust (0-25)
        id_signals = [r for r in all_signals if r.category == CATEGORY_IDENTITY_TRUST or r.signal_name.startswith("id_")]
        id_score = sum(r.score_impact for r in id_signals)
        cat_identity = min(CATEGORY_MAX_SCORES[CATEGORY_IDENTITY_TRUST], id_score)

        # 2. Transaction Anomaly (0-25) with Anti-Stacking
        # Correlated amount anomalies (spike 3x, p95 breach, large new transfer)
        # take the primary anomaly + small damped contribution for correlated triggers.
        txn_signals = [r for r in all_signals if r.category == CATEGORY_TRANSACTION_ANOMALY or r.signal_name.startswith("txn_")]
        if txn_signals:
            max_txn_impact = max(r.score_impact for r in txn_signals)
            extra_damped = 5 if len(txn_signals) > 1 else 0
            cat_txn = min(CATEGORY_MAX_SCORES[CATEGORY_TRANSACTION_ANOMALY], max_txn_impact + extra_damped)
        else:
            cat_txn = 0

        # 3. Behavioral Anomaly (0-25)
        beh_signals = [r for r in all_signals if r.category == CATEGORY_BEHAVIORAL_ANOMALY or r.signal_name.startswith("beh_")]
        beh_score = sum(r.score_impact for r in beh_signals) + behavior_score
        cat_beh = min(CATEGORY_MAX_SCORES[CATEGORY_BEHAVIORAL_ANOMALY], beh_score)

        # 4. Velocity / Network (0-15)
        vel_signals = [r for r in all_signals if r.category == CATEGORY_VELOCITY_NETWORK or r.signal_name.startswith("vel_")]
        vel_score = sum(r.score_impact for r in vel_signals)
        cat_vel = min(CATEGORY_MAX_SCORES[CATEGORY_VELOCITY_NETWORK], vel_score)

        # 5. ML Anomaly Contribution (0-10)
        # ML raw score range is [0, 30], scale linearly to [0, 10]
        cat_ml = min(
            CATEGORY_MAX_SCORES[CATEGORY_ML_ANOMALY],
            max(0, int(round(ml_score / 3.0)))
        )
        if cat_ml > 0:
            ml_signal = RiskReason(
                signal_name="ml_isolation_forest_anomaly",
                category=CATEGORY_ML_ANOMALY,
                reason=f"Machine Learning model identified multidimensional anomaly pattern (anomaly contribution: {cat_ml}/10)",
                severity=SignalSeverity.MEDIUM if cat_ml >= 6 else SignalSeverity.LOW,
                score_impact=cat_ml,
            )
            # Add ML signal to signal list if not already present
            if not any(r.signal_name == "ml_isolation_forest_anomaly" for r in all_signals):
                all_signals.append(ml_signal)

        # Historical baseline factor (damped into score, respecting total max 100)
        hist_contrib = min(5, max(0, historical_risk))

        total_score = min(
            TOTAL_MAX_SCORE,
            cat_identity + cat_txn + cat_beh + cat_vel + cat_ml + hist_contrib
        )

        # Determine Risk Level & Action
        if total_score <= 30:
            level = RiskLevel.LOW
        elif total_score <= 60:
            level = RiskLevel.MEDIUM
        elif total_score <= 80:
            level = RiskLevel.HIGH
        else:
            level = RiskLevel.CRITICAL

        decision = self.ACTIONS[level]

        category_scores = CategoryScores(
            identity_trust=cat_identity,
            transaction_anomaly=cat_txn,
            behavioral_anomaly=cat_beh,
            velocity_network=cat_vel,
            ml_anomaly=cat_ml,
        )

        # Identify primary risk driver
        dim_map = {
            CATEGORY_IDENTITY_TRUST: cat_identity,
            CATEGORY_TRANSACTION_ANOMALY: cat_txn,
            CATEGORY_BEHAVIORAL_ANOMALY: cat_beh,
            CATEGORY_VELOCITY_NETWORK: cat_vel,
            CATEGORY_ML_ANOMALY: cat_ml,
        }
        primary_driver = max(dim_map, key=dim_map.get) if total_score > 0 else "none"

        anti_stacking_applied = len(txn_signals) > 1 or (len(vel_signals) > 1 and sum(r.score_impact for r in vel_signals) > 15)

        explanation_data = {
            "primary_risk_driver": primary_driver,
            "anti_stacking_applied": anti_stacking_applied,
            "dimension_caps": CATEGORY_MAX_SCORES,
            "raw_ml_score": ml_score,
            "historical_risk_factor": hist_contrib,
            "context_summary": context_summary or {},
        }

        return CompositeRiskResult(
            score=total_score,
            level=level,
            decision=decision,
            signals=all_signals,
            category_scores=category_scores,
            explanation_data=explanation_data,
        )


# ---------------------------------------------------------------------------
# Risk Engine Orchestrator
# ---------------------------------------------------------------------------
class RiskEngine:
    def __init__(self):
        self.rule_engine = RuleEngine()
        self.baseline = BehavioralBaseline()
        self.ml_detector = MLAnomalyDetector()
        self.aggregator = RiskAggregator()

    async def evaluate(self, payer_id: str, merchant_id: str, amount: int) -> CompositeRiskResult:
        ctx = await self.baseline.get_context(payer_id, merchant_id, amount)

        rule_reasons = self.rule_engine.evaluate(ctx)

        features = self.ml_detector.extract_features(ctx)
        ml_score = self.ml_detector.predict(features)

        historical_risk = await self._get_historical_risk(payer_id)

        context_summary = {
            "amount": ctx.amount,
            "hour": ctx.hour,
            "is_new_recipient": ctx.is_new_recipient,
            "is_unverified_merchant": ctx.is_unverified_merchant,
            "txn_count_1h": ctx.txn_count_1h,
            "txn_count_24h": ctx.txn_count_24h,
            "avg_amount": ctx.avg_amount,
            "median_amount": ctx.median_amount,
            "p95_amount": ctx.p95_amount,
        }

        return self.aggregator.aggregate(
            rule_reasons=rule_reasons,
            behavior_score=0,
            ml_score=ml_score,
            historical_risk=historical_risk,
            context_summary=context_summary,
        )

    async def _get_historical_risk(self, payer_id: str) -> int:
        """Compute average historical risk factor for the payer from past decisions."""
        try:
            import numpy as np
            from app.services.supabase_client import get_supabase_admin

            supabase = get_supabase_admin()
            txn_resp = supabase.table("transactions").select("id").eq("payer_id", payer_id).limit(20).execute()
            if not txn_resp.data:
                return 0

            txn_ids = [t["id"] for t in txn_resp.data]
            decisions_resp = supabase.table("risk_decisions").select("score").in_("transaction_id", txn_ids).limit(20).execute()
            if decisions_resp.data:
                scores = [d["score"] for d in decisions_resp.data if d.get("score") is not None]
                if scores:
                    avg = float(np.mean(scores))
                    return min(5, int(avg * 0.05))
        except Exception:
            pass
        return 0


risk_engine = RiskEngine()