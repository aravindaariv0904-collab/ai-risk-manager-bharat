from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import math
import structlog

from app.models import RiskLevel, RiskAction, SignalSeverity
from app.schemas import RiskReason, CategoryScores, CompositeRiskOutput
from app.config import settings
from app.risk.ml_pipeline import (
    MLAnomalyDetector,
    CanonicalFeaturePipeline,
    CANONICAL_FEATURE_NAMES,
    CANONICAL_MODEL_VERSION,
)

logger = structlog.get_logger()

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
    risk level, decision, signals, category breakdown, recommended action,
    and human explanation.
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
        recommended_action: Optional[str] = None,
        human_explanation: Optional[str] = None,
    ):
        self.score = score
        self.level = level
        self.decision = decision
        self.action = decision  # alias for backward compat
        self.signals = signals
        self.reasons = signals   # alias for backward compat
        self.category_scores = category_scores
        self.explanation_data = explanation_data
        self.recommended_action = recommended_action or self._default_recommendation(decision)
        self.human_explanation = human_explanation or self._default_human_explanation(score, level, decision)
        self.explanation = self.human_explanation  # alias

    def _default_recommendation(self, decision: RiskAction) -> str:
        mapping = {
            RiskAction.ALLOW: "Allow payment to proceed directly.",
            RiskAction.STEP_UP_VERIFICATION: "Perform step-up verification (OTP / recipient confirm) before proceeding.",
            RiskAction.HOLD_FOR_REVIEW: "Hold payment for manual risk and compliance review.",
            RiskAction.BLOCK: "Block payment immediately to protect user from unauthorized loss.",
        }
        return mapping.get(decision, "Review risk signals before proceeding.")

    def _default_human_explanation(self, score: int, level: RiskLevel, decision: RiskAction) -> str:
        if decision == RiskAction.ALLOW:
            return f"Low risk score ({score}/100). The payment matches safe behavioral baseline."
        elif decision == RiskAction.STEP_UP_VERIFICATION:
            return f"Medium risk score ({score}/100). First-time recipient or unusual parameter detected; step-up verification required."
        elif decision == RiskAction.HOLD_FOR_REVIEW:
            return f"High risk score ({score}/100). Multiple anomalous patterns detected; payment is placed on hold for review."
        elif decision == RiskAction.BLOCK:
            return f"Critical risk score ({score}/100). Severe anomaly and fraud signals detected; payment blocked."
        return f"Payment evaluated with risk score {score}/100 ({level.value})."

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
            "recommended_action": self.recommended_action,
            "human_explanation": self.human_explanation,
            "explanation": self.explanation,
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
        from app.risk.behavioral import behavioral_baseline_engine

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
            if m_resp and m_resp.data:
                merchant_category = m_resp.data.get("business_category")
                profile = m_resp.data.get("risk_profile") or {}
                if isinstance(profile, dict) and profile.get("is_verified") is False:
                    is_unverified = True
        except Exception:
            pass

        # Compute robust behavioral baseline
        profile = behavioral_baseline_engine.compute_profile_from_history(
            payer_id=payer_id,
            historical_txns=recent_txns,
            reference_time=now,
        )

        return TransactionContext(
            amount=amount,
            currency="INR",
            merchant_id=merchant_id,
            payer_id=payer_id,
            hour=hour,
            day_of_week=day_of_week,
            is_new_recipient=is_new_recipient,
            is_unverified_merchant=is_unverified,
            txn_count_1h=profile.velocity_1h,
            txn_count_24h=profile.velocity_24h,
            txn_count_7d=profile.velocity_7d,
            failed_count_24h=profile.failed_count_24h,
            avg_amount=profile.mean_amount,
            median_amount=profile.median_amount,
            p95_amount=profile.p95_amount,
            frequent_merchants=profile.top_merchants,
            typical_hours=profile.typical_hours,
            merchant_category=merchant_category,
            merchant_category_history=profile.merchant_category_history,
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
    Defensible 0-100 Composite Risk Aggregator with Independent Dimensions,
    Configurable Thresholds, Structured Logging, and Anti-Stacking controls.

    Dimension Allocations:
      - Identity / Trust:       0 to 25
      - Transaction Anomaly:    0 to 25
      - Behavioral Anomaly:     0 to 25
      - Velocity / Network:     0 to 15
      - ML Anomaly:             0 to 10
      Total Maximum = 100

    Thresholds (Configurable via Settings):
      - 0  to 30:  LOW      -> ALLOW
      - 31 to 60:  MEDIUM   -> STEP_UP_VERIFICATION
      - 61 to 80:  HIGH     -> HOLD_FOR_REVIEW
      - 81 to 100: CRITICAL -> BLOCK
    """

    ACTIONS = {
        RiskLevel.LOW: RiskAction.ALLOW,
        RiskLevel.MEDIUM: RiskAction.STEP_UP_VERIFICATION,
        RiskLevel.HIGH: RiskAction.HOLD_FOR_REVIEW,
        RiskLevel.CRITICAL: RiskAction.BLOCK,
    }

    def __init__(
        self,
        low_max: Optional[int] = None,
        medium_max: Optional[int] = None,
        high_max: Optional[int] = None,
        critical_max: Optional[int] = None,
    ):
        self.low_max = low_max if low_max is not None else settings.RISK_THRESHOLD_LOW_MAX
        self.medium_max = medium_max if medium_max is not None else settings.RISK_THRESHOLD_MEDIUM_MAX
        self.high_max = high_max if high_max is not None else settings.RISK_THRESHOLD_HIGH_MAX
        self.critical_max = critical_max if critical_max is not None else settings.RISK_THRESHOLD_CRITICAL_MAX

    @property
    def thresholds(self) -> Dict[str, Tuple[int, int]]:
        return {
            "LOW": (0, self.low_max),
            "MEDIUM": (self.low_max + 1, self.medium_max),
            "HIGH": (self.medium_max + 1, self.high_max),
            "CRITICAL": (self.high_max + 1, self.critical_max),
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

        # Determine Risk Level & Action using configurable thresholds
        if total_score <= self.low_max:
            level = RiskLevel.LOW
        elif total_score <= self.medium_max:
            level = RiskLevel.MEDIUM
        elif total_score <= self.high_max:
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

        recommended_action = self._get_recommended_action(decision)
        human_explanation = self._get_human_explanation(total_score, level, decision, primary_driver, all_signals)

        explanation_data = {
            "primary_risk_driver": primary_driver,
            "anti_stacking_applied": anti_stacking_applied,
            "dimension_caps": CATEGORY_MAX_SCORES,
            "threshold_config": {
                "low_max": self.low_max,
                "medium_max": self.medium_max,
                "high_max": self.high_max,
                "critical_max": self.critical_max,
            },
            "raw_ml_score": ml_score,
            "historical_risk_factor": hist_contrib,
            "context_summary": context_summary or {},
        }

        # Structured Decision Logging (Requirement 6)
        logger.info(
            "Risk policy decision evaluated",
            score=total_score,
            level=level.value,
            decision=decision.value,
            primary_driver=primary_driver,
            signals_count=len(all_signals),
            recommended_action=recommended_action,
        )

        return CompositeRiskResult(
            score=total_score,
            level=level,
            decision=decision,
            signals=all_signals,
            category_scores=category_scores,
            explanation_data=explanation_data,
            recommended_action=recommended_action,
            human_explanation=human_explanation,
        )

    def _get_recommended_action(self, decision: RiskAction) -> str:
        rec_map = {
            RiskAction.ALLOW: "Allow transaction to proceed.",
            RiskAction.STEP_UP_VERIFICATION: "Perform step-up verification (OTP/recipient confirm) before proceeding.",
            RiskAction.HOLD_FOR_REVIEW: "Hold transaction for manual compliance review.",
            RiskAction.BLOCK: "Block transaction immediately to prevent fraudulent transfer.",
        }
        return rec_map.get(decision, "Review risk signals before proceeding.")

    def _get_human_explanation(
        self,
        score: int,
        level: RiskLevel,
        decision: RiskAction,
        primary_driver: str,
        signals: List[RiskReason],
    ) -> str:
        driver_desc = primary_driver.replace("_", " ") if primary_driver != "none" else ""
        if decision == RiskAction.ALLOW:
            return f"Low risk score ({score}/100). All payment indicators are within safe baseline."
        elif decision == RiskAction.STEP_UP_VERIFICATION:
            return f"Medium risk score ({score}/100). Elevated risk in {driver_desc}; secondary verification required before payment."
        elif decision == RiskAction.HOLD_FOR_REVIEW:
            return f"High risk score ({score}/100). Multiple anomalous patterns detected ({driver_desc}); payment is held for review."
        elif decision == RiskAction.BLOCK:
            return f"Critical risk score ({score}/100). High fraud indicators detected ({driver_desc}); transaction is blocked."
        return f"Risk evaluated with score {score}/100 ({level.value})."


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