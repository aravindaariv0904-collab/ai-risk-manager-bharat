import enum
from typing import Dict, Set, Union, Optional
import structlog

logger = structlog.get_logger()


class TransactionStatus(str, enum.Enum):
    CREATED = "CREATED"
    RISK_CHECKED = "RISK_CHECKED"
    VERIFICATION_REQUIRED = "VERIFICATION_REQUIRED"
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    FAILED = "FAILED"
    HELD = "HELD"
    BLOCKED = "BLOCKED"
    REFUNDED = "REFUNDED"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_str(cls, val: Optional[Union[str, "TransactionStatus"]]) -> "TransactionStatus":
        if val is None:
            return cls.UNKNOWN
        if isinstance(val, TransactionStatus):
            return val
        
        normalized = str(val).strip().upper()
        # Aliases & backwards-compatibility mapping
        alias_map = {
            "PENDING": cls.AUTHORIZED,
            "SUCCESS": cls.CAPTURED,
            "SUCCESSFUL": cls.CAPTURED,
            "BLOCKED_PAYMENT": cls.BLOCKED,
            "HOLD": cls.HELD,
            "HOLD_FOR_REVIEW": cls.HELD,
            "STEP_UP": cls.VERIFICATION_REQUIRED,
            "STEP_UP_VERIFICATION": cls.VERIFICATION_REQUIRED,
        }
        if normalized in alias_map:
            return alias_map[normalized]
        
        try:
            return cls(normalized)
        except ValueError:
            return cls.UNKNOWN


class InvalidStateTransitionError(ValueError):
    """Raised when an illegal transaction state transition is attempted."""
    def __init__(self, from_state: TransactionStatus, to_state: TransactionStatus, message: Optional[str] = None):
        self.from_state = from_state
        self.to_state = to_state
        msg = message or f"Illegal transaction state transition from '{from_state.value}' to '{to_state.value}'"
        super().__init__(msg)


# State Transition Rules Matrix
VALID_TRANSITIONS: Dict[TransactionStatus, Set[TransactionStatus]] = {
    TransactionStatus.CREATED: {
        TransactionStatus.CREATED,  # idempotent self-transition
        TransactionStatus.RISK_CHECKED,
        TransactionStatus.VERIFICATION_REQUIRED,
        TransactionStatus.AUTHORIZED,
        TransactionStatus.HELD,
        TransactionStatus.BLOCKED,
        TransactionStatus.FAILED,
    },
    TransactionStatus.RISK_CHECKED: {
        TransactionStatus.RISK_CHECKED,
        TransactionStatus.AUTHORIZED,
        TransactionStatus.VERIFICATION_REQUIRED,
        TransactionStatus.HELD,
        TransactionStatus.BLOCKED,
        TransactionStatus.FAILED,
    },
    TransactionStatus.VERIFICATION_REQUIRED: {
        TransactionStatus.VERIFICATION_REQUIRED,
        TransactionStatus.RISK_CHECKED,
        TransactionStatus.AUTHORIZED,
        TransactionStatus.HELD,
        TransactionStatus.BLOCKED,
        TransactionStatus.FAILED,
    },
    TransactionStatus.AUTHORIZED: {
        TransactionStatus.AUTHORIZED,
        TransactionStatus.CAPTURED,
        TransactionStatus.FAILED,
        TransactionStatus.HELD,
        TransactionStatus.REFUNDED,
    },
    TransactionStatus.HELD: {
        TransactionStatus.HELD,
        TransactionStatus.AUTHORIZED,
        TransactionStatus.CAPTURED,
        TransactionStatus.BLOCKED,
        TransactionStatus.FAILED,
    },
    TransactionStatus.CAPTURED: {
        TransactionStatus.CAPTURED,  # idempotent capture
        TransactionStatus.REFUNDED,
    },
    TransactionStatus.FAILED: {
        TransactionStatus.FAILED,  # idempotent fail
        TransactionStatus.CREATED,  # retry initiation
        TransactionStatus.UNKNOWN,
    },
    TransactionStatus.BLOCKED: {
        TransactionStatus.BLOCKED,  # terminal state
    },
    TransactionStatus.REFUNDED: {
        TransactionStatus.REFUNDED,  # terminal state
    },
    TransactionStatus.UNKNOWN: {
        TransactionStatus.UNKNOWN,
        TransactionStatus.CREATED,
        TransactionStatus.RISK_CHECKED,
        TransactionStatus.AUTHORIZED,
        TransactionStatus.CAPTURED,
        TransactionStatus.FAILED,
        TransactionStatus.HELD,
        TransactionStatus.BLOCKED,
    },
}

# Precedence ranking for out-of-order event protection (terminal/critical states take precedence)
STATE_PRECEDENCE: Dict[TransactionStatus, int] = {
    TransactionStatus.UNKNOWN: 0,
    TransactionStatus.CREATED: 1,
    TransactionStatus.RISK_CHECKED: 2,
    TransactionStatus.VERIFICATION_REQUIRED: 2,
    TransactionStatus.HELD: 3,
    TransactionStatus.AUTHORIZED: 4,
    TransactionStatus.FAILED: 5,
    TransactionStatus.BLOCKED: 5,
    TransactionStatus.CAPTURED: 6,
    TransactionStatus.REFUNDED: 7,
}


def normalize_transaction_status(status: Optional[Union[str, TransactionStatus]]) -> TransactionStatus:
    """Safely converts any status representation to canonical TransactionStatus."""
    return TransactionStatus.from_str(status)


def validate_transition(
    current_status: Optional[Union[str, TransactionStatus]],
    new_status: Union[str, TransactionStatus],
    allow_same_state: bool = True,
) -> bool:
    """
    Check if a transition from current_status to new_status is structurally valid.
    """
    curr = normalize_transaction_status(current_status)
    target = normalize_transaction_status(new_status)

    if curr == target:
        return allow_same_state

    allowed_next_states = VALID_TRANSITIONS.get(curr, set())
    return target in allowed_next_states


def transition_transaction(
    current_status: Optional[Union[str, TransactionStatus]],
    new_status: Union[str, TransactionStatus],
    strict: bool = True,
) -> TransactionStatus:
    """
    Validates and executes a state transition.
    If strict=True, raises InvalidStateTransitionError on invalid transition.
    If strict=False, logs a warning and returns current_status if invalid.
    """
    curr = normalize_transaction_status(current_status)
    target = normalize_transaction_status(new_status)

    if curr == target:
        return target

    # When strict=False (e.g. in event/webhook ingestion), prevent out-of-order event downgrade
    if not strict and curr == TransactionStatus.CAPTURED and target in {TransactionStatus.AUTHORIZED, TransactionStatus.CREATED, TransactionStatus.RISK_CHECKED}:
        logger.info(
            "Ignored out-of-order state downgrade for captured transaction",
            current_status=curr.value,
            attempted_status=target.value,
        )
        return curr

    if not validate_transition(curr, target):
        if strict:
            raise InvalidStateTransitionError(curr, target)
        logger.warning(
            "Invalid transaction state transition attempted",
            current_status=curr.value,
            attempted_status=target.value,
        )
        return curr

    return target
