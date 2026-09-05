import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.security.auth import get_current_user_id, get_current_user_role
from app.schemas import InvestigationAction

client = TestClient(app)

DUMMY_ADMIN_ID = "00000000-0000-0000-0000-000000000099"
DUMMY_TXN_ID = "00000000-0000-0000-0000-000000000055"


@pytest.fixture(autouse=True)
def auth_override():
    app.dependency_overrides[get_current_user_id] = lambda: DUMMY_ADMIN_ID
    app.dependency_overrides[get_current_user_role] = lambda: "admin"
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_supabase():
    with patch("app.api.admin.get_supabase_admin") as mock_admin:
        sb = MagicMock()
        mock_admin.return_value = sb
        yield sb


def test_investigate_approve_release(mock_supabase):
    txn_mock = MagicMock()
    txn_mock.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data={
            "id": DUMMY_TXN_ID,
            "status": "held",
            "razorpay_payment_id": "pay_xyz",
            "amount": 50000,
        }
    )
    mock_supabase.table.return_value = txn_mock

    response = client.post(
        f"/api/admin/transactions/{DUMMY_TXN_ID}/investigate",
        json={
            "action": InvestigationAction.APPROVE_RELEASE.value,
            "notes": "Verified genuine customer via direct phone confirmation.",
            "reviewer_role": "risk_analyst",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["transaction_id"] == DUMMY_TXN_ID
    assert data["action_taken"] == "APPROVE_RELEASE"
    assert data["previous_status"] == "held"
    assert data["new_status"] == "captured"


def test_investigate_mark_false_positive(mock_supabase):
    txn_mock = MagicMock()
    txn_mock.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data={
            "id": DUMMY_TXN_ID,
            "status": "held",
            "razorpay_payment_id": None,
            "amount": 25000,
        }
    )
    mock_supabase.table.return_value = txn_mock

    response = client.post(
        f"/api/admin/transactions/{DUMMY_TXN_ID}/investigate",
        json={
            "action": InvestigationAction.MARK_FALSE_POSITIVE.value,
            "notes": "Legitimate seasonal gift transfer.",
            "reviewer_role": "risk_lead",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["action_taken"] == "MARK_FALSE_POSITIVE"
    assert data["new_status"] == "authorized"


def test_investigate_confirm_fraud(mock_supabase):
    txn_mock = MagicMock()
    txn_mock.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data={
            "id": DUMMY_TXN_ID,
            "status": "held",
            "amount": 80000,
        }
    )
    mock_supabase.table.return_value = txn_mock

    response = client.post(
        f"/api/admin/transactions/{DUMMY_TXN_ID}/investigate",
        json={
            "action": InvestigationAction.CONFIRM_FRAUD.value,
            "notes": "Mule account confirmed via I4C directory.",
            "reviewer_role": "risk_lead",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["action_taken"] == "CONFIRM_FRAUD"
    assert data["new_status"] == "blocked"


def test_get_feedback_metrics(mock_supabase):
    # Mock feedback data (2 legitimate/FP, 3 confirmed fraud)
    fb_mock = MagicMock()
    fb_mock.select.return_value.execute.return_value = MagicMock(
        data=[
            {"label": "legitimate", "fraud_confirmed": False},
            {"label": "legitimate", "fraud_confirmed": False},
            {"label": "fraud", "fraud_confirmed": True},
            {"label": "fraud", "fraud_confirmed": True},
            {"label": "fraud", "fraud_confirmed": True},
        ]
    )

    # Mock pending count
    pending_mock = MagicMock()
    pending_mock.select.return_value.or_.return_value.execute.return_value = MagicMock(
        count=5
    )

    def table_side_effect(table_name):
        if table_name == "feedback":
            return fb_mock
        elif table_name == "transactions":
            return pending_mock
        return MagicMock()

    mock_supabase.table.side_effect = table_side_effect

    response = client.get("/api/admin/feedback-metrics")
    assert response.status_code == 200
    data = response.json()
    assert data["total_reviewed"] == 5
    assert data["false_positive_count"] == 2
    assert data["false_positive_rate"] == 0.4
    assert data["confirmed_fraud_count"] == 3
    assert data["confirmed_fraud_rate"] == 0.6
    assert data["pending_review_count"] == 5
    assert data["review_rate"] == 0.5  # 5 / (5 + 5)
