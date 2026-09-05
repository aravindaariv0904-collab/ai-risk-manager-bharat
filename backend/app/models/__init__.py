from sqlalchemy import Column, String, Integer, DateTime, Text, Enum, ForeignKey, Index, Boolean, BigInteger
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
import uuid
import enum

Base = declarative_base()


class UserRole(str, enum.Enum):
    CITIZEN = "citizen"
    MERCHANT = "merchant"
    ADMIN = "admin"


class Language(str, enum.Enum):
    EN = "en"
    HI = "hi"
    TA = "ta"


from app.payments.state_machine import TransactionStatus


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskAction(str, enum.Enum):
    ALLOW = "ALLOW"
    STEP_UP_VERIFICATION = "STEP_UP_VERIFICATION"
    HOLD_FOR_REVIEW = "HOLD_FOR_REVIEW"
    BLOCK = "BLOCK"
    VERIFY = "VERIFY"
    WARN = "WARN"


class SignalSeverity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class WebhookProcessingStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"
    DUPLICATE = "duplicate"


class FeedbackLabel(str, enum.Enum):
    LEGITIMATE = "legitimate"
    SUSPICIOUS = "suspicious"
    FRAUD = "fraud"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    auth_user_id = Column(UUID(as_uuid=True), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    phone = Column(String(20))
    role = Column(Enum(UserRole), nullable=False, default=UserRole.CITIZEN)
    language = Column(Enum(Language), nullable=False, default=Language.EN)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    merchant = relationship("Merchant", back_populates="user", uselist=False)
    payer_transactions = relationship("Transaction", foreign_keys="Transaction.payer_id", back_populates="payer")
    merchant_transactions = relationship("Transaction", foreign_keys="Transaction.merchant_id", back_populates="merchant")


class Merchant(Base):
    __tablename__ = "merchants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    business_name = Column(String(255), nullable=False)
    business_category = Column(String(100))
    risk_profile = Column(JSONB, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="merchant")
    transactions = relationship("Transaction", back_populates="merchant")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    razorpay_payment_id = Column(String(100), unique=True, index=True)
    razorpay_order_id = Column(String(100), index=True)
    payer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    merchant_id = Column(UUID(as_uuid=True), ForeignKey("merchants.id"), nullable=False, index=True)
    amount = Column(BigInteger, nullable=False)
    currency = Column(String(3), default="INR")
    status = Column(Enum(TransactionStatus), nullable=False, default=TransactionStatus.CREATED)
    risk_score = Column(Integer)
    risk_level = Column(Enum(RiskLevel))
    risk_action = Column(Enum(RiskAction))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    payer = relationship("User", foreign_keys=[payer_id], back_populates="payer_transactions")
    merchant = relationship("Merchant", back_populates="transactions")
    risk_events = relationship("RiskEvent", back_populates="transaction")
    risk_decision = relationship("RiskDecision", back_populates="transaction", uselist=False)


class RiskEvent(Base):
    __tablename__ = "risk_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=False, index=True)
    signal_name = Column(String(100), nullable=False)
    signal_value = Column(JSONB)
    severity = Column(Enum(SignalSeverity))
    score_impact = Column(Integer)
    reason = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    transaction = relationship("Transaction", back_populates="risk_events")


class RiskDecision(Base):
    __tablename__ = "risk_decisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id"), unique=True, nullable=False)
    score = Column(Integer, nullable=False)
    level = Column(Enum(RiskLevel), nullable=False)
    action = Column(Enum(RiskAction), nullable=False)
    explanation = Column(Text)
    category_scores = Column(JSONB, default={})
    explanation_data = Column(JSONB, default={})
    model_version = Column(String(20), default="v2.0")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    transaction = relationship("Transaction", back_populates="risk_decision")


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(String(100), unique=True, nullable=False, index=True)
    event_type = Column(String(50), nullable=False)
    payload_hash = Column(String(64), nullable=False)
    payment_id = Column(String(100), index=True)
    order_id = Column(String(100), index=True)
    processing_status = Column(Enum(WebhookProcessingStatus), default=WebhookProcessingStatus.PENDING, index=True)
    processing_error = Column(Text)
    received_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True))


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=False, index=True)
    label = Column(Enum(FeedbackLabel))
    fraud_confirmed = Column(Boolean)
    user_feedback = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# Indexes
Index("ix_transactions_payer_created", Transaction.payer_id, Transaction.created_at.desc())
Index("ix_transactions_merchant_created", Transaction.merchant_id, Transaction.created_at.desc())
Index("ix_risk_events_transaction", RiskEvent.transaction_id)
Index("ix_webhook_events_status", WebhookEvent.processing_status)