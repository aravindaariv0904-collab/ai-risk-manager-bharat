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
    return await explain_risk(request)


@router.post("/assistant", response_model=AssistantResponse)
async def ai_assistant(
    request: AssistantQuery,
    user_id: str = Depends(get_current_user_id),
):
    supabase = get_supabase_admin()

    user_resp = supabase.table("users").select("id, language").eq("auth_user_id", user_id).maybe_single().execute()
    if not user_resp.data:
        raise HTTPException(status_code=404, detail="User not found")

    language = user_resp.data.get("language", "en")

    txns = supabase.table("transactions").select("*").eq("payer_id", user_resp.data["id"]).order("created_at", desc=True).limit(10).execute()

    context = {
        "recent_transactions": txns.data or [],
        "user_id": user_resp.data["id"],
    }

    answer = await assistant_query(request.query, user_resp.data["id"], context, language)

    return AssistantResponse(answer=answer, data_sources=["transactions"])


@router.get("/transaction-summary/{transaction_id}")
async def transaction_summary(
    transaction_id: UUID,
    user_id: str = Depends(get_current_user_id),
):
    supabase = get_supabase_admin()

    user_resp = supabase.table("users").select("id, language").eq("auth_user_id", user_id).maybe_single().execute()
    if not user_resp.data:
        raise HTTPException(status_code=404, detail="User not found")

    txn = supabase.table("transactions").select("*").eq("id", str(transaction_id)).single().execute()
    if not txn.data:
        raise HTTPException(status_code=404, detail="Transaction not found")

    risk = supabase.table("risk_decisions").select("*").eq("transaction_id", str(transaction_id)).single().execute()

    merchant = supabase.table("merchants").select("business_name").eq("id", txn.data["merchant_id"]).single().execute()

    txn_data = {
        **txn.data,
        "merchant_name": merchant.data["business_name"] if merchant.data else "Unknown",
    }

    summary = await summarize_transaction_risk(
        txn_data,
        risk.data or {},
        user_resp.data.get("language", "en"),
    )

    return {"summary": summary}