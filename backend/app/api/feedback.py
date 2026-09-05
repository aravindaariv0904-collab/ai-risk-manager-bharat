from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID

from app.schemas import FeedbackCreate, FeedbackResponse
from app.security.auth import get_current_user_id
from app.services.supabase_client import get_supabase_admin

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackResponse)
async def create_feedback(
    request: FeedbackCreate,
    user_id: str = Depends(get_current_user_id),
):
    supabase = get_supabase_admin()

    # --- Resolve user profile ---
    try:
        user_resp = (
            supabase.table("users")
            .select("id")
            .eq("auth_user_id", user_id)
            .maybe_single()  # avoids PGRST116 on 0 rows
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}")

    if not user_resp.data:
        raise HTTPException(status_code=404, detail="User not found")

    # --- Verify transaction ownership ---
    try:
        txn = (
            supabase.table("transactions")
            .select("payer_id")
            .eq("id", str(request.transaction_id))
            .maybe_single()  # avoids PGRST116 on 0 rows
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}")

    if not txn.data or txn.data["payer_id"] != user_resp.data["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to provide feedback for this transaction")

    # --- Insert feedback ---
    try:
        feedback = supabase.table("feedback").insert({
            "transaction_id": str(request.transaction_id),
            "label": request.label,
            "fraud_confirmed": request.fraud_confirmed,
            "user_feedback": request.user_feedback,
        }).execute()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Failed to save feedback: {exc}")

    return FeedbackResponse(**feedback.data[0])