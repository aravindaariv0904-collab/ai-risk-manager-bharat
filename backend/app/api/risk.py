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
        raise HTTPException(status_code=404, detail="User profile not found")
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

    risk_score, risk_level, risk_action, reasons, details = await risk_engine.evaluate(
        payer_id=payer_id,
        merchant_id=str(request.merchant_id),
        amount=request.amount,
    )

    txn_insert = supabase.table("transactions").insert({
        "payer_id": payer_id,
        "merchant_id": str(request.merchant_id),
        "amount": request.amount,
        "currency": request.currency,
        "status": "created",
        "risk_score": risk_score,
        "risk_level": risk_level.value,
        "risk_action": risk_action.value,
    }).execute()

    transaction_id = txn_insert.data[0]["id"]

    for reason in reasons:
        supabase.table("risk_events").insert({
            "transaction_id": transaction_id,
            "signal_name": reason.signal_name,
            "signal_value": {},
            "severity": reason.severity.value,
            "score_impact": reason.score_impact,
            "reason": reason.reason,
        }).execute()

    supabase.table("risk_decisions").insert({
        "transaction_id": transaction_id,
        "score": risk_score,
        "level": risk_level.value,
        "action": risk_action.value,
        "model_version": "v1.0",
    }).execute()

    return RiskPrecheckResponse(
        transaction_id=transaction_id,
        risk_score=risk_score,
        risk_level=risk_level,
        risk_action=risk_action,
        reasons=reasons,
        recommended_action=risk_action.value.replace("_", " ").title(),
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
            reason=e["reason"],
            severity=SignalSeverity(e["severity"]),
            score_impact=e["score_impact"],
        )
        for e in (events_resp.data or [])
    ]

    return RiskDecisionResponse(
        transaction_id=transaction_id,
        score=decision["score"],
        level=RiskLevel(decision["level"]),
        action=RiskAction(decision["action"]),
        explanation=decision.get("explanation"),
        model_version=decision["model_version"],
        reasons=reasons,
        created_at=decision["created_at"],
    )


@router.post("/explain", response_model=ExplainRiskResponse)
async def explain_risk_endpoint(
    request: ExplainRiskRequest,
    user_id: str = Depends(get_current_user_id),
):
    return await explain_risk(request)