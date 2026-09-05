from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from datetime import datetime
from uuid import uuid4

from app.schemas import (
    ScenarioInfo, SimulatorRunResponse,
    CompositeRiskOutput, CategoryScores, RiskReason,
    RiskLevel, RiskAction, VerificationStatus,
)
from app.risk.engine import risk_engine, TransactionContext

router = APIRouter(prefix="/api/simulator", tags=["simulator"])

SCENARIOS: Dict[str, Dict[str, Any]] = {
    "normal_payment": {
        "id": "normal_payment",
        "name": "Normal Daily Utility / Grocery Payment",
        "description": "Routine ₹450 grocery transaction with an existing verified merchant during normal afternoon hours.",
        "category": "Baseline / Low Risk",
        "expected_risk_level": "LOW",
        "expected_action": "ALLOW",
        "context": TransactionContext(
            amount=45000,  # ₹450
            currency="INR",
            merchant_id="merchant-grocery-001",
            payer_id="citizen-user-001",
            hour=14,
            day_of_week=2,
            is_new_recipient=False,
            is_unverified_merchant=False,
            txn_count_1h=0,
            txn_count_24h=2,
            txn_count_7d=8,
            failed_count_24h=0,
            avg_amount=50000,
            median_amount=45000,
            p95_amount=120000,
            frequent_merchants=["merchant-grocery-001", "merchant-dairy-002"],
            typical_hours=[10, 11, 14, 18, 19],
            merchant_category="grocery",
            merchant_category_history=["grocery", "utilities"],
        ),
    },
    "first_time_high_value": {
        "id": "first_time_high_value",
        "name": "First-Time High-Value Late Night Payment",
        "description": "Sudden ₹85,000 transaction at 2:30 AM to a new unverified recipient; 17x higher than historical P95 baseline.",
        "category": "Anomaly Detection",
        "expected_risk_level": "HIGH",
        "expected_action": "HOLD_FOR_REVIEW",
        "context": TransactionContext(
            amount=8500000,  # ₹85,000
            currency="INR",
            merchant_id="merchant-unknown-999",
            payer_id="citizen-user-001",
            hour=2,  # 2 AM
            day_of_week=3,
            is_new_recipient=True,
            is_unverified_merchant=True,
            txn_count_1h=0,
            txn_count_24h=1,
            txn_count_7d=4,
            failed_count_24h=0,
            avg_amount=50000,
            median_amount=40000,
            p95_amount=150000,
            frequent_merchants=["merchant-grocery-001"],
            typical_hours=[9, 10, 14, 18],
            merchant_category="crypto_exchange",
            merchant_category_history=["grocery"],
        ),
    },
    "rapid_velocity_burst": {
        "id": "rapid_velocity_burst",
        "name": "Rapid Velocity Drain / Smurfing",
        "description": "6th consecutive transaction in 3 minutes with multiple recent failed attempts, triggering velocity & network tripwires.",
        "category": "Velocity / Account Takeover",
        "expected_risk_level": "CRITICAL",
        "expected_action": "BLOCK",
        "context": TransactionContext(
            amount=1500000,  # ₹15,000
            currency="INR",
            merchant_id="merchant-peer-transfers",
            payer_id="citizen-user-002",
            hour=23,
            day_of_week=5,
            is_new_recipient=True,
            is_unverified_merchant=True,
            txn_count_1h=6,
            txn_count_24h=14,
            txn_count_7d=25,
            failed_count_24h=3,
            avg_amount=100000,
            median_amount=80000,
            p95_amount=250000,
            frequent_merchants=["merchant-grocery-001"],
            typical_hours=[10, 11, 15, 16],
            merchant_category="p2p_transfer",
            merchant_category_history=["grocery", "utilities"],
        ),
    },
    "known_mule_account": {
        "id": "known_mule_account",
        "name": "Targeting Flagged Mule Beneficiary",
        "description": "High value payment directed towards a flagged high-risk recipient account with 0 trust score and multiple failed authentications.",
        "category": "Identity & Mule Protection",
        "expected_risk_level": "CRITICAL",
        "expected_action": "BLOCK",
        "context": TransactionContext(
            amount=4500000,  # ₹45,000
            currency="INR",
            merchant_id="mule-vpa-flagged-007",
            payer_id="citizen-user-003",
            hour=3,
            day_of_week=0,
            is_new_recipient=True,
            is_unverified_merchant=True,
            txn_count_1h=3,
            txn_count_24h=8,
            txn_count_7d=12,
            failed_count_24h=4,
            avg_amount=80000,
            median_amount=60000,
            p95_amount=200000,
            frequent_merchants=["merchant-local"],
            typical_hours=[12, 13, 17, 18],
            merchant_category="money_lender",
            merchant_category_history=["retail"],
        ),
    },
    "device_switch_high_amount": {
        "id": "device_switch_high_amount",
        "name": "Device Switch & High Amount Anomaly",
        "description": "Unrecognized hardware fingerprint + unusual operating hour attempting a ₹75,000 transfer, triggering ML anomaly + trust alarms.",
        "category": "Device & Session Security",
        "expected_risk_level": "CRITICAL",
        "expected_action": "BLOCK",
        "context": TransactionContext(
            amount=7500000,  # ₹75,000
            currency="INR",
            merchant_id="merchant-luxury-watch",
            payer_id="citizen-user-004",
            hour=1,
            day_of_week=6,
            is_new_recipient=True,
            is_unverified_merchant=True,
            txn_count_1h=1,
            txn_count_24h=2,
            txn_count_7d=3,
            failed_count_24h=2,
            avg_amount=40000,
            median_amount=30000,
            p95_amount=100000,
            frequent_merchants=["merchant-groceries"],
            typical_hours=[9, 10, 14, 15],
            merchant_category="luxury_goods",
            merchant_category_history=["grocery"],
        ),
    },
    "amount_tampering_mismatch": {
        "id": "amount_tampering_mismatch",
        "name": "Vendor Fake Screenshot / Amount Tampering",
        "description": "Simulates QR tampering where fraudster showed a fake ₹5,000 receipt for a real ₹50 transaction.",
        "category": "Vendor Protection / Fraud Claim",
        "expected_risk_level": "CRITICAL",
        "expected_action": "BLOCK",
        "context": TransactionContext(
            amount=500000,  # ₹5,000 claimed vs ₹50 actual
            currency="INR",
            merchant_id="merchant-chai-stall",
            payer_id="fraud-actor-001",
            hour=16,
            day_of_week=4,
            is_new_recipient=True,
            is_unverified_merchant=False,
            txn_count_1h=4,
            txn_count_24h=9,
            txn_count_7d=12,
            failed_count_24h=2,
            avg_amount=5000,
            median_amount=4000,
            p95_amount=15000,
            frequent_merchants=[],
            typical_hours=[10, 11, 16],
            merchant_category="tea_vendor",
            merchant_category_history=["food"],
        ),
        "is_amount_mismatch_demo": True,
    },
    "phishing_spoofed_vpa": {
        "id": "phishing_spoofed_vpa",
        "name": "Phishing Lookalike / Spoofed Merchant VPA",
        "description": "Payment routed to lookalike handle masquerading as a utility provider, triggering recipient novelty & category mismatch.",
        "category": "Phishing & Spoofing",
        "expected_risk_level": "HIGH",
        "expected_action": "HOLD_FOR_REVIEW",
        "context": TransactionContext(
            amount=2500000,  # ₹25,000
            currency="INR",
            merchant_id="spoofed-electricity-board-009",
            payer_id="citizen-user-005",
            hour=21,
            day_of_week=1,
            is_new_recipient=True,
            is_unverified_merchant=True,
            txn_count_1h=1,
            txn_count_24h=3,
            txn_count_7d=5,
            failed_count_24h=0,
            avg_amount=60000,
            median_amount=50000,
            p95_amount=180000,
            frequent_merchants=["bescom-official-001"],
            typical_hours=[10, 12, 15, 17],
            merchant_category="utility_lookalike",
            merchant_category_history=["utilities", "groceries"],
        ),
    },
}


@router.get("/scenarios", response_model=List[ScenarioInfo])
async def list_simulator_scenarios():
    """Returns the list of 7 deterministic test fraud scenarios."""
    return [
        ScenarioInfo(
            id=s["id"],
            name=s["name"],
            description=s["description"],
            category=s["category"],
            expected_risk_level=s["expected_risk_level"],
            expected_action=s["expected_action"],
        )
        for s in SCENARIOS.values()
    ]


@router.post("/run/{scenario_id}", response_model=SimulatorRunResponse)
async def run_simulator_scenario(scenario_id: str):
    """
    Executes a deterministic fraud scenario through the real backend composite risk engine.
    Tags output with is_demo: true and full risk signals.
    """
    scenario = SCENARIOS.get(scenario_id)
    if not scenario:
        raise HTTPException(
            status_code=404,
            detail=f"Scenario '{scenario_id}' not found. Available: {list(SCENARIOS.keys())}",
        )

    ctx: TransactionContext = scenario["context"]

    # Run through the canonical production Risk Engine
    eval_result = risk_engine.evaluate_context(ctx)

    verification_status = None
    if scenario.get("is_amount_mismatch_demo"):
        verification_status = VerificationStatus.AMOUNT_MISMATCH

    return SimulatorRunResponse(
        scenario_id=scenario["id"],
        scenario_name=scenario["name"],
        description=scenario["description"],
        is_demo=True,
        simulated_at=datetime.utcnow(),
        input_payload={
            "amount_paise": ctx.amount,
            "amount_inr": ctx.amount / 100,
            "hour": ctx.hour,
            "is_new_recipient": ctx.is_new_recipient,
            "is_unverified_merchant": ctx.is_unverified_merchant,
            "txn_count_1h": ctx.txn_count_1h,
            "failed_count_24h": ctx.failed_count_24h,
            "category": ctx.merchant_category,
        },
        risk_assessment=CompositeRiskOutput(
            score=eval_result.score,
            level=eval_result.level,
            decision=eval_result.decision,
            signals=eval_result.signals,
            category_scores=eval_result.category_scores,
            explanation_data=eval_result.explanation_data,
        ),
        verification_status=verification_status,
        demo_badge="DEMO SIMULATION — AI RISK MANAGER FOR BHARAT",
    )
