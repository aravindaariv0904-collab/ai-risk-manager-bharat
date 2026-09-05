"""
Enhanced Behavioral Baseline Engine for Bharat Digital Payments.

Calculates robust statistical profiles and baseline deviations from historical transactions:
- Median, Mean, P95, Q25, Q75, and Interquartile Range (IQR)
- Velocity (1h, 24h, 7d)
- Hourly activity distributions & typical payment hours
- Merchant / Counterparty frequency
- Failed payment ratio
- Recency of activity

Gracefully handles new users, low-activity users, high-activity users, and missing data
with explicit INSUFFICIENT_HISTORY handling without penalizing lack of history as fraud.
"""

from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import numpy as np
import structlog

logger = structlog.get_logger()

MIN_BASELINE_TRANSACTIONS = 3
DEFAULT_HISTORICAL_WINDOW_DAYS = 90


@dataclass
class BehavioralProfile:
    payer_id: str
    baseline_status: str  # "ESTABLISHED" | "INSUFFICIENT_HISTORY"
    txn_count: int
    window_days: int
    mean_amount: float
    median_amount: float
    p95_amount: float
    iqr_amount: float
    q25_amount: float
    q75_amount: float
    min_amount: float
    max_amount: float
    failed_ratio: float
    typical_hours: List[int]
    hourly_distribution: Dict[int, int]
    top_merchants: List[str]
    merchant_frequency: Dict[str, int]
    new_recipient_ratio: float
    last_activity_hours_ago: Optional[float]
    velocity_1h: int
    velocity_24h: int
    velocity_7d: int
    failed_count_24h: int
    merchant_category_history: List[str] = field(default_factory=list)


class BehavioralBaselineEngine:
    def __init__(self, window_days: int = DEFAULT_HISTORICAL_WINDOW_DAYS, min_baseline_txns: int = MIN_BASELINE_TRANSACTIONS):
        self.window_days = window_days
        self.min_baseline_txns = min_baseline_txns
        self._supabase = None

    @property
    def supabase(self):
        if self._supabase is None:
            from app.services.supabase_client import get_supabase_admin
            self._supabase = get_supabase_admin()
        return self._supabase

    def compute_profile_from_history(
        self,
        payer_id: str,
        historical_txns: List[Dict[str, Any]],
        reference_time: Optional[datetime] = None,
    ) -> BehavioralProfile:
        """
        Pure statistical computation of behavioral baseline from transaction records.
        Robust to empty lists, missing fields, single-item histories, and high-frequency accounts.
        """
        now = reference_time or datetime.utcnow()
        if now.tzinfo:
            now = now.replace(tzinfo=None)

        def parse_dt(val: Any) -> datetime:
            if isinstance(val, datetime):
                return val.replace(tzinfo=None) if val.tzinfo else val
            if isinstance(val, str):
                try:
                    return datetime.fromisoformat(val.replace("Z", "+00:00")).replace(tzinfo=None)
                except Exception:
                    pass
            return now

        # Filter transactions within historical window with valid positive amount
        cutoff = now - timedelta(days=self.window_days)
        valid_txns = []
        amounts = []
        for t in historical_txns:
            if not isinstance(t, dict):
                continue
            amt = t.get("amount")
            if amt is None:
                continue
            try:
                float_amt = float(amt)
                if float_amt <= 0:
                    continue
            except (ValueError, TypeError):
                continue

            created_at = parse_dt(t.get("created_at"))
            if created_at >= cutoff:
                valid_txns.append(t)
                amounts.append(float_amt)

        txn_count = len(valid_txns)

        # Check for sufficient history
        if txn_count < self.min_baseline_txns or len(amounts) < self.min_baseline_txns:
            # Insufficient History: Return safe baseline
            return self._build_insufficient_history_profile(payer_id, valid_txns, amounts, now, parse_dt)

        # 1. Robust Amount Statistics
        np_amounts = np.array(amounts)
        mean_val = float(np.mean(np_amounts))
        median_val = float(np.median(np_amounts))
        q25_val = float(np.percentile(np_amounts, 25))
        q75_val = float(np.percentile(np_amounts, 75))
        p95_val = float(np.percentile(np_amounts, 95))
        min_val = float(np.min(np_amounts))
        max_val = float(np.max(np_amounts))
        iqr_val = float(max(0.0, q75_val - q25_val))

        # 2. Hourly Activity Distribution
        hours = [parse_dt(t.get("created_at")).hour for t in valid_txns]
        hour_counts: Dict[int, int] = {}
        for h in hours:
            hour_counts[h] = hour_counts.get(h, 0) + 1
        typical_hours = sorted(hour_counts, key=hour_counts.get, reverse=True)[:4]

        # 3. Velocity & Time Delays
        txn_count_1h = len([t for t in valid_txns if (now - parse_dt(t.get("created_at"))).total_seconds() <= 3600])
        txn_count_24h = len([t for t in valid_txns if (now - parse_dt(t.get("created_at"))).total_seconds() <= 86400])
        txn_count_7d = len([t for t in valid_txns if (now - parse_dt(t.get("created_at"))).total_seconds() <= 604800])

        failed_txns = [t for t in valid_txns if str(t.get("status", "")).upper() in {"FAILED"}]
        failed_count_24h = len([
            t for t in failed_txns
            if (now - parse_dt(t.get("created_at"))).total_seconds() <= 86400
        ])
        failed_ratio = float(len(failed_txns) / txn_count) if txn_count > 0 else 0.0

        # 4. Merchant Frequency & Top Contacts
        merchant_counts: Dict[str, int] = {}
        merchant_categories: List[str] = []
        for t in valid_txns:
            mid = t.get("merchant_id")
            if mid:
                merchant_counts[mid] = merchant_counts.get(mid, 0) + 1
            cat = t.get("merchant_category") or t.get("category")
            if cat and cat not in merchant_categories:
                merchant_categories.append(cat)

        top_merchants = sorted(merchant_counts, key=merchant_counts.get, reverse=True)[:5]

        # New recipient ratio (merchants transacted with only once)
        single_txn_merchants = sum(1 for count in merchant_counts.values() if count == 1)
        new_recipient_ratio = float(single_txn_merchants / len(merchant_counts)) if merchant_counts else 0.0

        # Last activity
        last_dt = max((parse_dt(t.get("created_at")) for t in valid_txns), default=None)
        last_activity_hours = (now - last_dt).total_seconds() / 3600.0 if last_dt else None

        return BehavioralProfile(
            payer_id=payer_id,
            baseline_status="ESTABLISHED",
            txn_count=txn_count,
            window_days=self.window_days,
            mean_amount=mean_val,
            median_amount=median_val,
            p95_amount=p95_val,
            iqr_amount=iqr_val,
            q25_amount=q25_val,
            q75_amount=q75_val,
            min_amount=min_val,
            max_amount=max_val,
            failed_ratio=failed_ratio,
            typical_hours=typical_hours,
            hourly_distribution=hour_counts,
            top_merchants=top_merchants,
            merchant_frequency=merchant_counts,
            new_recipient_ratio=new_recipient_ratio,
            last_activity_hours_ago=last_activity_hours,
            velocity_1h=txn_count_1h,
            velocity_24h=txn_count_24h,
            velocity_7d=txn_count_7d,
            failed_count_24h=failed_count_24h,
            merchant_category_history=merchant_categories,
        )

    def _build_insufficient_history_profile(
        self,
        payer_id: str,
        valid_txns: List[Dict],
        amounts: List[float],
        now: datetime,
        parse_dt: Any,
    ) -> BehavioralProfile:
        """Constructs a non-penalizing baseline for new or low-activity users."""
        txn_count = len(valid_txns)
        mean_val = float(np.mean(amounts)) if amounts else 0.0
        median_val = float(np.median(amounts)) if amounts else 0.0
        p95_val = float(np.percentile(amounts, 95)) if amounts else 0.0
        min_val = min(amounts) if amounts else 0.0
        max_val = max(amounts) if amounts else 0.0

        txn_count_1h = len([t for t in valid_txns if (now - parse_dt(t.get("created_at"))).total_seconds() <= 3600])
        txn_count_24h = len([t for t in valid_txns if (now - parse_dt(t.get("created_at"))).total_seconds() <= 86400])
        txn_count_7d = len([t for t in valid_txns if (now - parse_dt(t.get("created_at"))).total_seconds() <= 604800])

        failed_txns = [t for t in valid_txns if str(t.get("status", "")).upper() in {"FAILED"}]
        failed_count_24h = len([
            t for t in failed_txns
            if (now - parse_dt(t.get("created_at"))).total_seconds() <= 86400
        ])

        return BehavioralProfile(
            payer_id=payer_id,
            baseline_status="INSUFFICIENT_HISTORY",
            txn_count=txn_count,
            window_days=self.window_days,
            mean_amount=mean_val,
            median_amount=median_val,
            p95_amount=p95_val,
            iqr_amount=0.0,
            q25_amount=min_val,
            q75_amount=max_val,
            min_amount=min_val,
            max_amount=max_val,
            failed_ratio=0.0,
            typical_hours=[],
            hourly_distribution={},
            top_merchants=[],
            merchant_frequency={},
            new_recipient_ratio=1.0 if txn_count == 0 else 0.5,
            last_activity_hours_ago=None,
            velocity_1h=txn_count_1h,
            velocity_24h=txn_count_24h,
            velocity_7d=txn_count_7d,
            failed_count_24h=failed_count_24h,
            merchant_category_history=[],
        )

    async def get_profile_for_payer(self, payer_id: str) -> BehavioralProfile:
        """Fetch history and compute profile efficiently."""
        try:
            cutoff = (datetime.utcnow() - timedelta(days=self.window_days)).isoformat()
            res = (
                self.supabase.table("transactions")
                .select("amount, created_at, status, merchant_id")
                .eq("payer_id", payer_id)
                .gte("created_at", cutoff)
                .order("created_at", desc=True)
                .limit(200)
                .execute()
            )
            history = res.data or []
            return self.compute_profile_from_history(payer_id, history)
        except Exception as e:
            logger.warning("Failed to fetch historical transactions from DB for baseline", payer_id=payer_id, error=str(e))
            return self.compute_profile_from_history(payer_id, [])


behavioral_baseline_engine = BehavioralBaselineEngine()
