from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from datetime import datetime, timedelta

from app.schemas import (
    AdminDashboardResponse, ChartDataPoint,
    RiskDistributionResponse, TransactionVolumeResponse,
)
from app.security.auth import get_current_user_id, get_current_user_role
from app.services.supabase_client import get_supabase_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/dashboard", response_model=AdminDashboardResponse)
async def admin_dashboard(
    user_id: str = Depends(get_current_user_id),
    role: str = Depends(get_current_user_role),
):
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    supabase = get_supabase_admin()

    total = supabase.table("transactions").select("id", count="exact").execute()
    low = supabase.table("transactions").select("id", count="exact").eq("risk_level", "LOW").execute()
    medium = supabase.table("transactions").select("id", count="exact").eq("risk_level", "MEDIUM").execute()
    high = supabase.table("transactions").select("id", count="exact").eq("risk_level", "HIGH").execute()
    suspicious = supabase.table("transactions").select("id", count="exact").eq("risk_level", "HIGH").execute()
    verified = supabase.table("transactions").select("id", count="exact").eq("status", "captured").execute()

    return AdminDashboardResponse(
        total_transactions=total.count or 0,
        low_risk=low.count or 0,
        medium_risk=medium.count or 0,
        high_risk=high.count or 0,
        suspicious_count=suspicious.count or 0,
        verified_payments=verified.count or 0,
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
        date = txn["created_at"][:10]
        daily_counts[date] = daily_counts.get(date, 0) + 1

    sorted_dates = sorted(daily_counts.keys())
    return TransactionVolumeResponse(data=[
        ChartDataPoint(label=date, value=daily_counts[date])
        for date in sorted_dates
    ])