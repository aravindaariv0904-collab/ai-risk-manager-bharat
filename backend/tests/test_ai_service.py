import pytest
from app.ai.service import explain_risk, FALLBACK_TEMPLATES, RECOMMENDATIONS
from app.schemas import ExplainRiskRequest, RiskLevel, Language, RiskReason, SignalSeverity


@pytest.mark.asyncio
async def test_explain_risk_fallback_en_critical():
    req = ExplainRiskRequest(
        risk_score=92,
        risk_level=RiskLevel.CRITICAL,
        reasons=[
            RiskReason(
                signal_name="known_mule_account",
                category="identity_trust",
                reason="Recipient VPA reported in cybercrime mule database",
                severity=SignalSeverity.HIGH,
                score_impact=25,
            )
        ],
        language=Language.EN,
    )
    res = await explain_risk(req)
    assert res.explanation is not None
    assert "Critical risk of fraud detected" in res.explanation or "mule" in res.explanation
    assert "Do not complete payment" in res.recommendation or "blocked" in res.recommendation


@pytest.mark.asyncio
async def test_explain_risk_fallback_hi_high():
    req = ExplainRiskRequest(
        risk_score=75,
        risk_level=RiskLevel.HIGH,
        reasons=[
            RiskReason(
                signal_name="unusual_hour",
                category="behavioral_anomaly",
                reason="Payment attempted at 2:00 AM",
                severity=SignalSeverity.HIGH,
                score_impact=15,
            )
        ],
        language=Language.HI,
    )
    res = await explain_risk(req)
    assert res.explanation is not None
    assert "जोखिम" in res.explanation
    assert "सत्यापित करें" in res.recommendation


@pytest.mark.asyncio
async def test_explain_risk_fallback_ta_low():
    req = ExplainRiskRequest(
        risk_score=15,
        risk_level=RiskLevel.LOW,
        reasons=[],
        language=Language.TA,
    )
    res = await explain_risk(req)
    assert res.explanation is not None
    assert "பாதுகாப்பாக" in res.explanation
    assert "தொடரவும்" in res.recommendation
