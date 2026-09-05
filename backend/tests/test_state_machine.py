import pytest
from app.payments.state_machine import (
    TransactionStatus,
    InvalidStateTransitionError,
    validate_transition,
    transition_transaction,
    normalize_transaction_status,
)


class TestTransactionStateMachine:
    def test_normalize_transaction_status(self):
        assert normalize_transaction_status("CREATED") == TransactionStatus.CREATED
        assert normalize_transaction_status("created") == TransactionStatus.CREATED
        assert normalize_transaction_status("pending") == TransactionStatus.AUTHORIZED
        assert normalize_transaction_status("PENDING") == TransactionStatus.AUTHORIZED
        assert normalize_transaction_status("captured") == TransactionStatus.CAPTURED
        assert normalize_transaction_status("CAPTURED") == TransactionStatus.CAPTURED
        assert normalize_transaction_status("failed") == TransactionStatus.FAILED
        assert normalize_transaction_status("refunded") == TransactionStatus.REFUNDED
        assert normalize_transaction_status("STEP_UP_VERIFICATION") == TransactionStatus.VERIFICATION_REQUIRED
        assert normalize_transaction_status("HOLD_FOR_REVIEW") == TransactionStatus.HELD
        assert normalize_transaction_status(None) == TransactionStatus.UNKNOWN
        assert normalize_transaction_status("non_existent_state") == TransactionStatus.UNKNOWN

    def test_valid_standard_lifecycle_transitions(self):
        # CREATED -> RISK_CHECKED -> AUTHORIZED -> CAPTURED -> REFUNDED
        s1 = transition_transaction(TransactionStatus.CREATED, TransactionStatus.RISK_CHECKED)
        assert s1 == TransactionStatus.RISK_CHECKED

        s2 = transition_transaction(s1, TransactionStatus.AUTHORIZED)
        assert s2 == TransactionStatus.AUTHORIZED

        s3 = transition_transaction(s2, TransactionStatus.CAPTURED)
        assert s3 == TransactionStatus.CAPTURED

        s4 = transition_transaction(s3, TransactionStatus.REFUNDED)
        assert s4 == TransactionStatus.REFUNDED

    def test_valid_step_up_verification_flow(self):
        # CREATED -> VERIFICATION_REQUIRED -> AUTHORIZED -> CAPTURED
        s1 = transition_transaction(TransactionStatus.CREATED, TransactionStatus.VERIFICATION_REQUIRED)
        assert s1 == TransactionStatus.VERIFICATION_REQUIRED

        s2 = transition_transaction(s1, TransactionStatus.AUTHORIZED)
        assert s2 == TransactionStatus.AUTHORIZED

        s3 = transition_transaction(s2, TransactionStatus.CAPTURED)
        assert s3 == TransactionStatus.CAPTURED

    def test_valid_held_and_review_flow(self):
        # CREATED -> HELD -> AUTHORIZED -> CAPTURED
        s1 = transition_transaction(TransactionStatus.CREATED, TransactionStatus.HELD)
        assert s1 == TransactionStatus.HELD

        s2 = transition_transaction(s1, TransactionStatus.AUTHORIZED)
        assert s2 == TransactionStatus.AUTHORIZED

        # Or HELD directly to BLOCKED
        s_blocked = transition_transaction(TransactionStatus.HELD, TransactionStatus.BLOCKED)
        assert s_blocked == TransactionStatus.BLOCKED

    def test_valid_blocked_flow(self):
        s1 = transition_transaction(TransactionStatus.CREATED, TransactionStatus.BLOCKED)
        assert s1 == TransactionStatus.BLOCKED

        # BLOCKED is terminal
        with pytest.raises(InvalidStateTransitionError):
            transition_transaction(TransactionStatus.BLOCKED, TransactionStatus.CAPTURED)

    def test_valid_failure_and_retry(self):
        s1 = transition_transaction(TransactionStatus.AUTHORIZED, TransactionStatus.FAILED)
        assert s1 == TransactionStatus.FAILED

        # Failed allows retry to CREATED
        s2 = transition_transaction(s1, TransactionStatus.CREATED)
        assert s2 == TransactionStatus.CREATED

    def test_idempotent_self_transitions(self):
        assert transition_transaction(TransactionStatus.CAPTURED, TransactionStatus.CAPTURED) == TransactionStatus.CAPTURED
        assert transition_transaction(TransactionStatus.AUTHORIZED, TransactionStatus.AUTHORIZED) == TransactionStatus.AUTHORIZED
        assert transition_transaction(TransactionStatus.FAILED, TransactionStatus.FAILED) == TransactionStatus.FAILED

    def test_invalid_transitions_raise_error(self):
        # Cannot regress from CAPTURED to CREATED
        with pytest.raises(InvalidStateTransitionError):
            transition_transaction(TransactionStatus.CAPTURED, TransactionStatus.CREATED)

        # Cannot jump from BLOCKED to CAPTURED
        with pytest.raises(InvalidStateTransitionError):
            transition_transaction(TransactionStatus.BLOCKED, TransactionStatus.CAPTURED)

        # Cannot regress from REFUNDED to AUTHORIZED or CAPTURED
        with pytest.raises(InvalidStateTransitionError):
            transition_transaction(TransactionStatus.REFUNDED, TransactionStatus.AUTHORIZED)

        with pytest.raises(InvalidStateTransitionError):
            transition_transaction(TransactionStatus.REFUNDED, TransactionStatus.CAPTURED)

    def test_out_of_order_event_protection(self):
        # If a transaction is already CAPTURED, a late-arriving AUTHORIZED or CREATED event must not downgrade state
        res = transition_transaction(TransactionStatus.CAPTURED, TransactionStatus.AUTHORIZED, strict=False)
        assert res == TransactionStatus.CAPTURED

        res2 = transition_transaction(TransactionStatus.CAPTURED, TransactionStatus.CREATED, strict=False)
        assert res2 == TransactionStatus.CAPTURED
