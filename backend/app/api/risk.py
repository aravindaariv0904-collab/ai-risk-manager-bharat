from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from typing import List

from app.schemas import (
    RiskPrecheckRequest, RiskPrecheckResponse,
    RiskDecisionResponse, ExplainRiskRequest, ExplainRiskResponse,
    RiskReason, RiskLevel, RiskAction, SignalSeverity,
)
from app.security.auth import get_current_user_id
from app.risk.engine import risk_engine
from app.ai.service import explain_risk
from app.services.supabase_client import get_supabase_admin
from app.models import RiskDecision, RiskEvent, SignalSeverity as ModelSignalSeverity

router = APIRouter(prefix="/api/risk", tags=["risk"])


@router.post("/precheck", response_model=RiskPrecheckResponse)
async def risk_precheck(
    request: RiskPrecheckRequest,
    user_id: str = Depends(get_current_user_id),
):
    supabase = get_supabase_admin()

    user_resp = supabase.table("users").select("id").eq("auth_user_id", user_id).maybe_single().execute()
    if not user_resp.data:
        payer_id = "d83675e1-4899-4671-81a2-c76e921cb9c8"
    else:
        payer_id = user_resp.data["id"]

    merchant_resp = supabase.table("merchants").select("id").eq("id", str(request.merchant_id)).maybe_single().execute()
    if not merchant_resp.data:
        new_m = {
            "id": str(request.merchant_id),
            "user_id": None,
            "business_name": "Unverified Recipient",
            "business_category": "Direct Transfer",
            "risk_profile": {"is_verified": False, "baseline_safety": "unverified_mobile_transfer"}
        }
        try:
            supabase.table("merchants").insert(new_m).execute()
        except Exception:
            pass

    eval_res = await risk_engine.evaluate(
        payer_id=payer_id,
        merchant_id=str(request.merchant_id),
        amount=request.amount,
    )

    # Map risk decision to explicit transaction state
    initial_status = "RISK_CHECKED"
    if eval_res.decision in [RiskAction.BLOCK]:
        initial_status = "BLOCKED"
    elif eval_res.decision in [RiskAction.HOLD_FOR_REVIEW, RiskAction.WARN]:
        initial_status = "HELD"
    elif eval_res.decision in [RiskAction.STEP_UP_VERIFICATION, RiskAction.VERIFY]:
        initial_status = "VERIFICATION_REQUIRED"
    elif eval_res.decision in [RiskAction.ALLOW]:
        initial_status = "RISK_CHECKED"

    txn_insert = supabase.table("transactions").insert({
        "payer_id": payer_id,
        "merchant_id": str(request.merchant_id),
        "amount": request.amount,
        "currency": request.currency,
        "status": initial_status,
        "risk_score": eval_res.score,
        "risk_level": eval_res.level.value,
        "risk_action": eval_res.decision.value,
    }).execute()

    transaction_id = txn_insert.data[0]["id"]

    for reason in eval_res.signals:
        supabase.table("risk_events").insert({
            "transaction_id": transaction_id,
            "signal_name": reason.signal_name,
            "signal_value": {"category": reason.category} if reason.category else {},
            "severity": reason.severity.value,
            "score_impact": reason.score_impact,
            "reason": reason.reason,
        }).execute()

    supabase.table("risk_decisions").insert({
        "transaction_id": transaction_id,
        "score": eval_res.score,
        "level": eval_res.level.value,
        "action": eval_res.decision.value,
        "explanation": eval_res.human_explanation,
        "category_scores": eval_res.category_scores.model_dump(),
        "explanation_data": eval_res.explanation_data,
        "model_version": "v2.0",
    }).execute()

    return RiskPrecheckResponse(
        transaction_id=transaction_id,
        risk_score=eval_res.score,
        risk_level=eval_res.level,
        risk_action=eval_res.decision,
        reasons=eval_res.signals,
        category_scores=eval_res.category_scores,
        explanation_data=eval_res.explanation_data,
        recommended_action=eval_res.recommended_action,
        explanation=eval_res.human_explanation,
        human_explanation=eval_res.human_explanation,
        model_version="v2.0",
    )


@router.get("/{transaction_id}", response_model=RiskDecisionResponse)
async def get_risk_decision(
    transaction_id: UUID,
    user_id: str = Depends(get_current_user_id),
):
    supabase = get_supabase_admin()

    decision_resp = supabase.table("risk_decisions").select("*").eq("transaction_id", str(transaction_id)).maybe_single().execute()
    if not decision_resp.data:
        raise HTTPException(status_code=404, detail="Risk decision not found")

    decision = decision_resp.data

    events_resp = supabase.table("risk_events").select("*").eq("transaction_id", str(transaction_id)).execute()
    reasons = [
        RiskReason(
            signal_name=e["signal_name"],
            category=(e.get("signal_value") or {}).get("category"),
            reason=e["reason"],
            severity=SignalSeverity(e["severity"]),
            score_impact=e["score_impact"],
        )
        for e in (events_resp.data or [])
    ]

    cat_scores = None
    if decision.get("category_scores"):
        try:
            cat_scores = CategoryScores(**decision["category_scores"])
        except Exception:
            pass

    return RiskDecisionResponse(
        transaction_id=transaction_id,
        score=decision["score"],
        level=RiskLevel(decision["level"]),
        action=RiskAction(decision["action"]),
        explanation=decision.get("explanation"),
        human_explanation=decision.get("explanation"),
        recommended_action=decision.get("action", "").replace("_", " ").title(),
        category_scores=cat_scores,
        explanation_data=decision.get("explanation_data"),
        model_version=decision.get("model_version", "v2.0"),
        reasons=reasons,
        created_at=decision.get("created_at"),
    )


@router.post("/explain", response_model=ExplainRiskResponse)
async def explain_risk_endpoint(
    request: ExplainRiskRequest,
    user_id: str = Depends(get_current_user_id),
):
    return await explain_risk(request)