from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from uuid import UUID

from app.schemas import TransactionResponse, TransactionListResponse
from app.security.auth import get_current_user_id
from app.services.supabase_client import get_supabase_admin

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("", response_model=TransactionListResponse)
async def list_transactions(
    user_id: str = Depends(get_current_user_id),
    limit: int = 20,
    offset: int = 0,
    status: Optional[str] = None,
):
    supabase = get_supabase_admin()

    user_resp = supabase.table("users").select("id").eq("auth_user_id", user_id).single().execute()
    if not user_resp.data:
        raise HTTPException(status_code=404, detail="User profile not found")
    payer_id = user_resp.data["id"]

    query = supabase.table("transactions").select("*", count="exact").eq("payer_id", payer_id).order("created_at", desc=True).range(offset, offset + limit - 1)
    if status:
        query = query.eq("status", status)

    result = query.execute()

    return TransactionListResponse(
        transactions=[TransactionResponse(**t) for t in (result.data or [])],
        total=result.count or 0,
    )


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: UUID,
    user_id: str = Depends(get_current_user_id),
):
    supabase = get_supabase_admin()

    result = supabase.table("transactions").select("*").eq("id", str(transaction_id)).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Transaction not found")

    return TransactionResponse(**result.data)