from fastapi import APIRouter, Depends, HTTPException
from typing import List

from app.schemas import MerchantResponse
from app.security.auth import get_current_user_id
from app.services.supabase_client import get_supabase_admin

router = APIRouter(prefix="/api/merchants", tags=["merchants"])


@router.get("", response_model=List[MerchantResponse])
async def list_merchants(user_id: str = Depends(get_current_user_id)):
    supabase = get_supabase_admin()
    result = supabase.table("merchants").select("*").order("business_name").execute()
    return [MerchantResponse(**m) for m in (result.data or [])]


@router.get("/{merchant_id}", response_model=MerchantResponse)
async def get_merchant(
    merchant_id: str,
    user_id: str = Depends(get_current_user_id),
):
    supabase = get_supabase_admin()
    result = supabase.table("merchants").select("*").eq("id", merchant_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Merchant not found")
    return MerchantResponse(**result.data)