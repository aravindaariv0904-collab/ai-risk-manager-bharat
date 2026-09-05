import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.security.auth import get_current_user_id, get_current_user_role
from app.schemas import VerificationStatus

client = TestClient(app)

DUMMY_USER_ID = "00000000-0000-0000-0000-000000000001"
DUMMY_MERCHANT_ID = "00000000-0000-0000-0000-000000000002"
DUMMY_TXN_ID = "00000000-0000-0000-0000-000000000003"


@pytest.fixture(autouse=True)
def auth_override():
    app.dependency_overrides[get_current_user_id] = lambda: DUMMY_USER_ID
    app.dependency_overrides[get_current_user_role] = lambda: "merchant"
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_supabase():
    with patch("app.api.vendor.get_supabase_admin") as mock_admin:
        sb = MagicMock()
        mock_admin.return_value = sb

        # Mock user & merchant lookups
        def table_router(table_name):
            t = MagicMock()
            if table_name == "users":
                t.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
                    data={"id": DUMMY_USER_ID, "name": "Test User"}
                )
                t.select.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=[{"id": DUMMY_USER_ID, "name": "Test User"}]
                )
            elif table_name == "merchants":
                t.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
                    data={"id": DUMMY_MERCHANT_ID, "business_name": "Test Store"}
                )
            return t

        sb.table.side_effect = table_router
        yield sb


def test_verify_payment_by_id_captured(mock_supabase):
    txn_mock = MagicMock()
    txn_mock.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{
            "id": DUMMY_TXN_ID,
            "razorpay_payment_id": "pay_test123",
            "amount": 50000,
            "status": "captured",
            "risk_level": "LOW",
            "updated_at": "2026-09-05T12:00:00Z",
        }]
    )
    mock_supabase.table.side_effect = lambda t: txn_mock if t == "transactions" else MagicMock(
        select=MagicMock(return_value=MagicMock(eq=MagicMock(return_value=MagicMock(single=MagicMock(return_value=MagicMock(data={"id": DUMMY_USER_ID}))))))
    )

    response = client.get("/api/vendor/payment-verification/pay_test123")
    assert response.status_code == 200
    data = response.json()
    assert data["verified"] is True
    assert data["verification_status"] == VerificationStatus.VERIFIED.value
    assert data["amount"] == 50000


def test_verify_payment_by_details_amount_mismatch(mock_supabase):
    txn_mock = MagicMock()
    txn_mock.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{
            "id": DUMMY_TXN_ID,
            "razorpay_payment_id": "pay_mismatch123",
            "amount": 5000, # Actual ₹50
            "status": "captured",
            "risk_level": "LOW",
        }]
    )
    mock_supabase.table.side_effect = lambda t: txn_mock if t == "transactions" else MagicMock(
        select=MagicMock(return_value=MagicMock(eq=MagicMock(return_value=MagicMock(single=MagicMock(return_value=MagicMock(data={"id": DUMMY_USER_ID})))))),
        insert=MagicMock(return_value=MagicMock(execute=MagicMock(return_value=MagicMock(data=[]))))
    )

    # Merchant claims ₹500 (50000 paise)
    response = client.post("/api/vendor/payment-verification", json={
        "payment_id": "pay_mismatch123",
        "amount": 50000
    })
    assert response.status_code == 200
    data = response.json()
    assert data["verified"] is False
    assert data["verification_status"] == VerificationStatus.AMOUNT_MISMATCH.value
    assert data["amount_mismatch"] is True
    assert data["claimed_amount"] == 50000
    assert data["amount"] == 5000


def test_verify_payment_refunded(mock_supabase):
    txn_mock = MagicMock()
    txn_mock.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{
            "id": DUMMY_TXN_ID,
            "razorpay_payment_id": "pay_refunded123",
            "amount": 10000,
            "status": "refunded",
        }]
    )
    mock_supabase.table.side_effect = lambda t: txn_mock if t == "transactions" else MagicMock(
        select=MagicMock(return_value=MagicMock(eq=MagicMock(return_value=MagicMock(single=MagicMock(return_value=MagicMock(data={"id": DUMMY_USER_ID}))))))
    )

    response = client.get("/api/vendor/payment-verification/pay_refunded123")
    assert response.status_code == 200
    data = response.json()
    assert data["verified"] is False
    assert data["verification_status"] == VerificationStatus.REFUNDED.value
