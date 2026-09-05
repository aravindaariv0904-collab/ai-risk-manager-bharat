from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, Dict, Any
from uuid import UUID

from app.schemas import AssistantQuery, AssistantResponse, ExplainRiskRequest, ExplainRiskResponse
from app.security.auth import get_current_user_id
from app.ai.service import explain_risk, assistant_query, summarize_transaction_risk
from app.services.supabase_client import get_supabase_admin

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/explain-risk", response_model=ExplainRiskResponse)
async def explain_risk_endpoint(
    request: ExplainRiskRequest,
    user_id: str = Depends(get_current_user_id),
):
    try:
        return await explain_risk(request)
    except Exception as exc:
        # Gemini/AI failure — return a safe fallback rather than 500
        return ExplainRiskResponse(
            explanation="AI analysis is temporarily unavailable. Please try again later.",
            risk_level="unknown",
            confidence=0.0,
        )


@router.post("/assistant", response_model=AssistantResponse)
async def ai_assistant(
    request: AssistantQuery,
    user_id: str = Depends(get_current_user_id),
):
    supabase = get_supabase_admin()

    # --- Resolve user ---
    try:
        user_resp = (
            supabase.table("users")
            .select("id, language")
            .eq("auth_user_id", user_id)
            .maybe_single()
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}")

    if not user_resp.data:
        raise HTTPException(status_code=404, detail="User not found")

    language = user_resp.data.get("language", "en")

    # --- Fetch recent transactions (non-fatal if DB is slow) ---
    recent_txns: list = []
    try:
        txns = (
            supabase.table("transactions")
            .select("*")
            .eq("payer_id", user_resp.data["id"])
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
        recent_txns = txns.data or []
    except Exception:
        pass  # Proceed without transaction context

    context = {
        "recent_transactions": recent_txns,
        "user_id": user_resp.data["id"],
    }

    # --- Call AI (fallback on failure) ---
    try:
        answer = await assistant_query(request.query, user_resp.data["id"], context, language)
    except Exception:
        answer = "AI assistant is temporarily unavailable. Please try again later."

    return AssistantResponse(answer=answer, data_sources=["transactions"])


@router.get("/transaction-summary/{transaction_id}")
async def transaction_summary(
    transaction_id: UUID,
    user_id: str = Depends(get_current_user_id),
):
    supabase = get_supabase_admin()

    # --- Resolve user ---
    try:
        user_resp = (
            supabase.table("users")
            .select("id, language")
            .eq("auth_user_id", user_id)
            .maybe_single()
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}")

    if not user_resp.data:
        raise HTTPException(status_code=404, detail="User not found")

    # --- Fetch transaction ---
    try:
        txn = (
            supabase.table("transactions")
            .select("*")
            .eq("id", str(transaction_id))
            .maybe_single()  # avoids PGRST116 on 0 rows
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}")

    if not txn.data:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # --- Fetch risk decision (non-fatal) ---
    risk_data: dict = {}
    try:
        risk = (
            supabase.table("risk_decisions")
            .select("*")
            .eq("transaction_id", str(transaction_id))
            .maybe_single()
            .execute()
        )
        risk_data = risk.data or {}
    except Exception:
        pass  # Proceed without risk data

    # --- Fetch merchant name (non-fatal) ---
    merchant_name = "Unknown"
    try:
        merchant = (
            supabase.table("merchants")
            .select("business_name")
            .eq("id", txn.data["merchant_id"])
            .maybe_single()
            .execute()
        )
        if merchant.data:
            merchant_name = merchant.data["business_name"]
    except Exception:
        pass  # Use default merchant name

    txn_data = {
        **txn.data,
        "merchant_name": merchant_name,
    }

    # --- Call AI (fallback on failure) ---
    try:
        summary = await summarize_transaction_risk(
            txn_data,
            risk_data,
            user_resp.data.get("language", "en"),
        )
    except Exception:
        summary = "AI summary is temporarily unavailable. Please try again later."

    return {"summary": summary}