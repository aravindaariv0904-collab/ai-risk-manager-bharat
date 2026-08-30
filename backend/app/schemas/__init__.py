import enum
from typing import List, Optional, Dict
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class Language(str, enum.Enum):
    EN = "en"
    HI = "hi"
    TA = "ta"


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RiskAction(str, enum.Enum):
    ALLOW = "ALLOW"
    VERIFY = "VERIFY"
    WARN = "WARN"
    BLOCK = "BLOCK"


class SignalSeverity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class PrecheckModes(str, enum.Enum):
    FAST = "fast"
    STANDARD = "standard"


class RiskReason(BaseModel):
    signal_name: str
    reason: str
    severity: SignalSeverity
    score_impact: int = Field(ge=0, le=100)


# ---- Risk precheck ----
class RiskPrecheckRequest(BaseModel):
    amount: int = Field(gt=0)
    currency: str = "INR"
    merchant_id: UUID
    mode: PrecheckModes = PrecheckModes.STANDARD
    device_id: Optional[str] = None
    user_agent: Optional[str] = None
    ip: Optional[str] = None


class RiskPrecheckResponse(BaseModel):
    transaction_id: UUID
    risk_score: int = Field(ge=0, le=100)
    risk_level: RiskLevel
    risk_action: RiskAction
    reasons: List[RiskReason] = Field(default_factory=list)
    recommended_action: str
    model_version: str = "v1.0"
    processing_time_ms: Optional[int] = None


class RiskDecisionResponse(BaseModel):
    transaction_id: UUID
    score: int = Field(ge=0, le=100)
    level: RiskLevel
    action: RiskAction
    explanation: Optional[str] = None
    model_version: str
    reasons: List[RiskReason] = Field(default_factory=list)
    created_at: Optional[datetime] = None


# ---- AI explanations ----
class ExplainRiskRequest(BaseModel):
    risk_score: int = Field(ge=0, le=100)
    risk_level: RiskLevel
    reasons: List[RiskReason] = Field(default_factory=list)
    language: Language = Language.EN


class ExplainRiskResponse(BaseModel):
    explanation: str
    recommendation: str


class AssistantQuery(BaseModel):
    query: str = Field(min_length=1)


class AssistantResponse(BaseModel):
    answer: str
    data_sources: List[str] = Field(default_factory=list)


# ---- Feedback ----
class FeedbackCreate(BaseModel):
    transaction_id: UUID
    label: str = Field(pattern="^(legitimate|suspicious|fraud)$")
    fraud_confirmed: Optional[bool] = None
    user_feedback: Optional[str] = None


class FeedbackResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: Optional[str] = None
    transaction_id: Optional[str] = None
    label: Optional[str] = None
    fraud_confirmed: Optional[bool] = None
    user_feedback: Optional[str] = None
    created_at: Optional[datetime] = None


# ---- Payments ----
class CreateOrderRequest(BaseModel):
    amount: int = Field(gt=0, lt=2**40)
    currency: str = "INR"
    merchant_id: UUID
    payment_method: Optional[str] = None


class CreateOrderResponse(BaseModel):
    order_id: str
    amount: int
    currency: str
    key_id: str
    receipt: Optional[str] = None


class PaymentStatusResponse(BaseModel):
    payment_id: str
    order_id: Optional[str] = None
    amount: Optional[int] = None
    status: Optional[str] = None
    method: Optional[str] = None
    captured_at: Optional[str] = None
    error_code: Optional[str] = None


# ---- Transactions ----
class TransactionResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: Optional[str] = None
    razorpay_payment_id: Optional[str] = None
    razorpay_order_id: Optional[str] = None
    payer_id: Optional[str] = None
    merchant_id: Optional[str] = None
    amount: Optional[int] = None
    currency: Optional[str] = None
    status: Optional[str] = None
    risk_score: Optional[int] = None
    risk_level: Optional[str] = None
    risk_action: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TransactionListResponse(BaseModel):
    transactions: List[TransactionResponse] = Field(default_factory=list)
    total: int = 0


# ---- Vendor ----
class SuspiciousClaim(BaseModel):
    transaction_id: Optional[str] = None
    amount: Optional[int] = None
    customer_name: Optional[str] = None
    claimed_at: Optional[str] = None
    risk_level: Optional[str] = None


class RiskAlert(BaseModel):
    transaction_id: Optional[str] = None
    type: Optional[str] = None
    message: Optional[str] = None
    severity: Optional[str] = None
    created_at: Optional[str] = None


class VendorDashboardResponse(BaseModel):
    today_collections: int = 0
    successful_count: int = 0
    pending_count: int = 0
    suspicious_claims: List[SuspiciousClaim] = Field(default_factory=list)
    risk_alerts: List[RiskAlert] = Field(default_factory=list)


class PaymentVerificationRequest(BaseModel):
    payment_id: Optional[str] = None
    amount: Optional[int] = None
    customer_phone: Optional[str] = None


class PaymentVerificationResponse(BaseModel):
    verified: bool
    payment_id: Optional[str] = None
    amount: Optional[int] = None
    status: Optional[str] = None
    captured_at: Optional[str] = None
    risk_level: Optional[str] = None
    message: str


# ---- Merchants ----
class MerchantResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: Optional[str] = None
    user_id: Optional[str] = None
    business_name: Optional[str] = None
    business_category: Optional[str] = None
    phone: Optional[str] = None
    upi_id: Optional[str] = None
    is_verified: bool = False
    risk_profile: Optional[Dict] = None
    created_at: Optional[datetime] = None


# ---- Admin ----
class ChartDataPoint(BaseModel):
    label: str
    value: int


class AdminDashboardResponse(BaseModel):
    total_transactions: int = 0
    verified_payments: int = 0
    low_risk: int = 0
    medium_risk: int = 0
    high_risk: int = 0
    suspicious_count: int = 0
    unverified_claims: int = 0


class RiskDistributionResponse(BaseModel):
    data: List[ChartDataPoint] = Field(default_factory=list)


class TransactionVolumeResponse(BaseModel):
    data: List[ChartDataPoint] = Field(default_factory=list)