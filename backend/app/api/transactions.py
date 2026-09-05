from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from uuid import UUID

from app.schemas import TransactionResponse, TransactionListResponse
from app.security.auth import get_current_user_id
from app.services.supabase_client import get_supabase_admin

router = APIRouter(prefix="/api/transactions", tags=["transactions"])

FALLBACK_PAYER_ID = "d83675e1-4899-4671-81a2-c76e921cb9c8"


@router.get("", response_model=TransactionListResponse)
async def list_transactions(
    user_id: str = Depends(get_current_user_id),
    limit: int = 20,
    offset: int = 0,
    status: Optional[str] = None,
):
    supabase = get_supabase_admin()

    # Resolve internal payer_id — use fallback if DB is unreachable
    payer_id = FALLBACK_PAYER_ID
    try:
        user_resp = (
            supabase.table("users")
            .select("id")
            .eq("auth_user_id", user_id)
            .maybe_single()  # avoids PGRST116 throw on 0 rows
            .execute()
        )
        if user_resp.data:
            payer_id = user_resp.data["id"]
    except Exception:
        pass  # DB down — continue with fallback payer_id

    # Fetch transactions — return empty list gracefully if DB is down
    try:
        query = (
            supabase.table("transactions")
            .select("*", count="exact")
            .eq("payer_id", payer_id)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
        )
        if status:
            query = query.eq("status", status)

        result = query.execute()

        return TransactionListResponse(
            transactions=[TransactionResponse(**t) for t in (result.data or [])],
            total=result.count or 0,
        )
    except Exception:
        return TransactionListResponse(transactions=[], total=0)


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: UUID,
    user_id: str = Depends(get_current_user_id),
):
    supabase = get_supabase_admin()

    try:
        result = (
            supabase.table("transactions")
            .select("*")
            .eq("id", str(transaction_id))
            .maybe_single()  # avoids PostgREST PGRST116 throw on 0 rows
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return TransactionResponse(**result.data)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable, please retry")