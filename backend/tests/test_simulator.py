import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_list_simulator_scenarios():
    response = client.get("/api/simulator/scenarios")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 7
    scenario_ids = [s["id"] for s in data]
    assert "normal_payment" in scenario_ids
    assert "first_time_high_value" in scenario_ids
    assert "rapid_velocity_burst" in scenario_ids
    assert "known_mule_account" in scenario_ids
    assert "device_switch_high_amount" in scenario_ids
    assert "amount_tampering_mismatch" in scenario_ids
    assert "phishing_spoofed_vpa" in scenario_ids


def test_run_normal_payment_scenario():
    response = client.post("/api/simulator/run/normal_payment")
    assert response.status_code == 200
    data = response.json()
    assert data["is_demo"] is True
    assert data["scenario_id"] == "normal_payment"
    assert data["risk_assessment"]["level"] in ["LOW", "MEDIUM"]
    assert data["risk_assessment"]["decision"] in ["ALLOW", "STEP_UP_VERIFICATION"]
    assert "DEMO SIMULATION" in data["demo_badge"]


def test_run_high_value_late_night_scenario():
    response = client.post("/api/simulator/run/first_time_high_value")
    assert response.status_code == 200
    data = response.json()
    assert data["is_demo"] is True
    assert data["risk_assessment"]["score"] >= 40
    assert len(data["risk_assessment"]["signals"]) > 0


def test_run_amount_tampering_scenario():
    response = client.post("/api/simulator/run/amount_tampering_mismatch")
    assert response.status_code == 200
    data = response.json()
    assert data["verification_status"] == "AMOUNT_MISMATCH"


def test_run_invalid_scenario_404():
    response = client.post("/api/simulator/run/non_existent_scenario")
    assert response.status_code == 404
