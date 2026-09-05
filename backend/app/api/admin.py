from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from datetime import datetime, timedelta

from app.schemas import (
    AdminDashboardResponse, ChartDataPoint,
    RiskDistributionResponse, TransactionVolumeResponse,
    InvestigationAction, InvestigationRequest, InvestigationResponse,
    FeedbackMetricsResponse, TransactionResponse,
)
from app.security.auth import get_current_user_id, get_current_user_role
from app.services.supabase_client import get_supabase_admin
from app.payments.state_machine import transition_transaction, TransactionStatus

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/dashboard", response_model=AdminDashboardResponse)
async def admin_dashboard(
    user_id: str = Depends(get_current_user_id),
    role: str = Depends(get_current_user_role),
):
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    supabase = get_supabase_admin()

    try:
        total = supabase.table("transactions").select("id", count="exact").execute()
        low = supabase.table("transactions").select("id", count="exact").eq("risk_level", "LOW").execute()
        medium = supabase.table("transactions").select("id", count="exact").eq("risk_level", "MEDIUM").execute()
        high = supabase.table("transactions").select("id", count="exact").eq("risk_level", "HIGH").execute()
        suspicious = supabase.table("transactions").select("id", count="exact").eq("risk_level", "HIGH").execute()
        verified = supabase.table("transactions").select("id", count="exact").eq("status", "captured").execute()
        unverified = supabase.table("transactions").select("id", count="exact").neq("status", "captured").execute()

        return AdminDashboardResponse(
            total_transactions=total.count or 0,
            low_risk=low.count or 0,
            medium_risk=medium.count or 0,
            high_risk=high.count or 0,
            suspicious_count=suspicious.count or 0,
            verified_payments=verified.count or 0,
            unverified_claims=unverified.count or 0,
        )
    except Exception:
        return AdminDashboardResponse(
            total_transactions=0,
            low_risk=0,
            medium_risk=0,
            high_risk=0,
            suspicious_count=0,
            verified_payments=0,
            unverified_claims=0,
        )


@router.get("/risk-distribution", response_model=RiskDistributionResponse)
async def risk_distribution(
    user_id: str = Depends(get_current_user_id),
    role: str = Depends(get_current_user_role),
):
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    supabase = get_supabase_admin()

    low = supabase.table("transactions").select("id", count="exact").eq("risk_level", "LOW").execute()
    medium = supabase.table("transactions").select("id", count="exact").eq("risk_level", "MEDIUM").execute()
    high = supabase.table("transactions").select("id", count="exact").eq("risk_level", "HIGH").execute()

    return RiskDistributionResponse(data=[
        ChartDataPoint(label="LOW", value=low.count or 0),
        ChartDataPoint(label="MEDIUM", value=medium.count or 0),
        ChartDataPoint(label="HIGH", value=high.count or 0),
    ])


@router.get("/transaction-volume", response_model=TransactionVolumeResponse)
async def transaction_volume(
    days: int = Query(30, ge=1, le=365),
    user_id: str = Depends(get_current_user_id),
    role: str = Depends(get_current_user_role),
):
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    supabase = get_supabase_admin()

    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    result = supabase.table("transactions").select("created_at").gte("created_at", cutoff).execute()

    daily_counts = {}
    for txn in (result.data or []):
        raw_val = txn.get("created_at")
        if isinstance(raw_val, datetime):
            date = raw_val.strftime("%Y-%m-%d")
        elif isinstance(raw_val, str):
            date = raw_val[:10]
        else:
            continue
        daily_counts[date] = daily_counts.get(date, 0) + 1

    sorted_dates = sorted(daily_counts.keys())
    return TransactionVolumeResponse(data=[
        ChartDataPoint(label=date, value=daily_counts[date])
        for date in sorted_dates
    ])


@router.get("/investigations/queue")
async def get_investigations_queue(
    user_id: str = Depends(get_current_user_id),
    role: str = Depends(get_current_user_role),
    limit: int = 50,
):
    """Retrieve queue of transactions requiring human fraud analysis and review."""
    if role not in ["admin", "risk_analyst"]:
        raise HTTPException(status_code=403, detail="Admin or Analyst access required")

    supabase = get_supabase_admin()

    # Query transactions that are held, verification required, or high/critical risk
    txns = (
        supabase.table("transactions")
        .select("*")
        .or_("risk_level.eq.HIGH,risk_level.eq.CRITICAL,risk_action.eq.HOLD_FOR_REVIEW,status.eq.held")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )

    return {"queue": txns.data or [], "count": len(txns.data or [])}


@router.post("/transactions/{transaction_id}/investigate", response_model=InvestigationResponse)
async def investigate_transaction(
    transaction_id: str,
    request: InvestigationRequest,
    user_id: str = Depends(get_current_user_id),
    role: str = Depends(get_current_user_role),
):
    """
    Execute an analyst review action on a flagged transaction.
    Records audit trail and closes false positive feedback loops.
    """
    if role not in ["admin", "risk_analyst"]:
        raise HTTPException(status_code=403, detail="Admin or Analyst access required")

    supabase = get_supabase_admin()

    # Fetch transaction
    txn_resp = supabase.table("transactions").select("*").eq("id", transaction_id).single().execute()
    if not txn_resp.data:
        raise HTTPException(status_code=404, detail="Transaction not found")

    txn = txn_resp.data
    previous_status = txn.get("status", "created")

    # Map investigation action to state machine update
    if request.action == InvestigationAction.APPROVE_RELEASE:
        new_status = "captured" if txn.get("razorpay_payment_id") else "authorized"
        event_name = "INVESTIGATION_APPROVE_RELEASE"
        user_feedback_label = "legitimate"
        is_fraud = False
        message = "Transaction approved and released for processing."

    elif request.action == InvestigationAction.MARK_FALSE_POSITIVE:
        new_status = "captured" if txn.get("razorpay_payment_id") else "authorized"
        event_name = "INVESTIGATION_FALSE_POSITIVE"
        user_feedback_label = "legitimate"
        is_fraud = False
        message = "Flagged alert marked as False Positive. Transaction released."

    elif request.action == InvestigationAction.CONFIRM_FRAUD:
        new_status = "blocked"
        event_name = "INVESTIGATION_CONFIRM_FRAUD"
        user_feedback_label = "fraud"
        is_fraud = True
        message = "Transaction confirmed as fraudulent and blocked."

    elif request.action == InvestigationAction.KEEP_ON_HOLD:
        new_status = "held"
        event_name = "INVESTIGATION_KEEP_ON_HOLD"
        user_feedback_label = "suspicious"
        is_fraud = None
        message = "Transaction kept on hold pending further external verification."

    # 1. Update transaction status
    try:
        supabase.table("transactions").update({
            "status": new_status,
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("id", transaction_id).execute()
    except Exception:
        pass

    # 2. Record feedback entry for ML retraining / precision metrics
    try:
        supabase.table("feedback").insert({
            "transaction_id": transaction_id,
            "label": user_feedback_label,
            "fraud_confirmed": is_fraud,
            "user_feedback": f"[{request.reviewer_role}] {request.notes}",
        }).execute()
    except Exception:
        pass

    # 3. Record audit log
    try:
        supabase.table("transaction_audits").insert({
            "transaction_id": transaction_id,
            "event_name": event_name,
            "actor": user_id,
            "details": {
                "reviewer_role": request.reviewer_role,
                "notes": request.notes,
                "previous_status": previous_status,
                "new_status": new_status,
                "action": request.action.value,
            },
        }).execute()
    except Exception:
        pass

    return InvestigationResponse(
        transaction_id=transaction_id,
        action_taken=request.action,
        previous_status=previous_status,
        new_status=new_status,
        reviewer_id=user_id,
        reviewer_role=request.reviewer_role,
        timestamp=datetime.utcnow(),
        message=message,
    )


@router.get("/feedback-metrics", response_model=FeedbackMetricsResponse)
async def get_feedback_metrics(
    user_id: str = Depends(get_current_user_id),
    role: str = Depends(get_current_user_role),
):
    """
    Returns governance and ML feedback metrics:
    false positive rate, confirmed fraud rate, and analyst review coverage.
    """
    if role not in ["admin", "risk_analyst"]:
        raise HTTPException(status_code=403, detail="Admin access required")

    supabase = get_supabase_admin()

    # Query all feedback records
    feedback_resp = supabase.table("feedback").select("label, fraud_confirmed").execute()
    feedback_data = feedback_resp.data or []

    total_reviewed = len(feedback_data)
    false_positives = len([f for f in feedback_data if f.get("label") == "legitimate" or f.get("fraud_confirmed") is False])
    confirmed_frauds = len([f for f in feedback_data if f.get("label") == "fraud" or f.get("fraud_confirmed") is True])

    fp_rate = round(false_positives / total_reviewed, 4) if total_reviewed > 0 else 0.0
    fraud_rate = round(confirmed_frauds / total_reviewed, 4) if total_reviewed > 0 else 0.0

    # Query pending review count
    pending_resp = (
        supabase.table("transactions")
        .select("id", count="exact")
        .or_("status.eq.held,risk_action.eq.HOLD_FOR_REVIEW")
        .execute()
    )
    pending_count = pending_resp.count or 0

    total_flagged_all = total_reviewed + pending_count
    review_rate = round(total_reviewed / total_flagged_all, 4) if total_flagged_all > 0 else 1.0

    return FeedbackMetricsResponse(
        total_reviewed=total_reviewed,
        false_positive_count=false_positives,
        false_positive_rate=fp_rate,
        confirmed_fraud_count=confirmed_frauds,
        confirmed_fraud_rate=fraud_rate,
        review_rate=review_rate,
        pending_review_count=pending_count,
    )