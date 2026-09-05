from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID

from app.security.auth import get_current_user_id
from app.payments.verification import verification_service

router = APIRouter(prefix="/api/verification", tags=["verification"])


class CreateChallengeRequest(BaseModel):
    transaction_id: UUID
    challenge_type: Optional[str] = "OTP_STEP_UP"
    recipient_hint: Optional[str] = None


class VerifyChallengeRequest(BaseModel):
    transaction_id: UUID
    challenge_id: UUID
    user_response: str = Field(min_length=1, max_length=50)


class VerificationStatusResponse(BaseModel):
    transaction_id: UUID
    challenge_id: Optional[str] = None
    status: str
    challenge_type: Optional[str] = None
    message: str
    verified: bool = False
    demo_otp_hint: Optional[str] = None


@router.post("/challenge")
async def create_verification_challenge(
    request: CreateChallengeRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    Generate a server-authoritative step-up verification challenge for a transaction.
    """
    try:
        res = await verification_service.create_challenge(
            transaction_id=str(request.transaction_id),
            challenge_type=request.challenge_type,
            recipient_hint=request.recipient_hint,
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Challenge creation failed: {str(e)}")


@router.post("/verify")
async def verify_challenge_endpoint(
    request: VerifyChallengeRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    Verify the user-supplied verification code / confirmation response.
    Enforces time limits, maximum attempts, and advances transaction state upon success.
    """
    try:
        res = await verification_service.verify_challenge(
            transaction_id=str(request.transaction_id),
            challenge_id=str(request.challenge_id),
            user_response=request.user_response,
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Verification failed: {str(e)}")
