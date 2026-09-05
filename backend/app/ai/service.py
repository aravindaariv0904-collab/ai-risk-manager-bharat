from typing import Optional
from app.config import settings
from app.schemas import ExplainRiskRequest, ExplainRiskResponse, RiskLevel, Language
import structlog

logger = structlog.get_logger()

_model = None


def _get_model():
    global _model
    if _model is None:
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        _model = genai.GenerativeModel("gemini-1.5-flash")
    return _model


LANGUAGE_NAMES = {
    Language.EN: "English",
    Language.HI: "Hindi",
    Language.TA: "Tamil",
}

FALLBACK_TEMPLATES: dict[Language, dict[str, str]] = {
    Language.EN: {
        "LOW": "This payment appears normal. You can proceed safely.",
        "MEDIUM": "This payment has some unusual patterns. Please verify the recipient before proceeding.",
        "HIGH": "This payment looks risky. We strongly recommend verifying the recipient before continuing.",
        "CRITICAL": "Critical risk of fraud detected. This payment is blocked to protect your funds.",
    },
    Language.HI: {
        "LOW": "यह भुगतान सामान्य लगता है। आप सुरक्षित रूप से आगे बढ़ सकते हैं।",
        "MEDIUM": "इस भुगतान में कुछ असामान्य पैटर्न हैं। कृपया आगे बढ़ने से पहले प्राप्तकर्ता को सत्यापित करें।",
        "HIGH": "यह भुगतान जोखिम भरा लगता है। जारी रखने से पहले प्राप्तकर्ता को सत्यापित करें।",
        "CRITICAL": "धोखाधड़ी का गंभीर जोखिम पाया गया। आपके पैसों की सुरक्षा के लिए यह भुगतान रोक दिया गया है।",
    },
    Language.TA: {
        "LOW": "இந்தக் கட்டணம் இயல்பானது. நீங்கள் பாதுகாப்பாகத் தொடரலாம்.",
        "MEDIUM": "இந்தக் கட்டணத்தில் சில அசாதாரண வடிவங்கள் உள்ளன. தொடரும் முன் பெறுபவரை சரிபார்க்கவும்.",
        "HIGH": "இந்தக் கட்டணம் ஆபத்தானது. தொடரும் முன் பெறுபவரை சரிபார்க்க வலியுறுத்துகிறோம்.",
        "CRITICAL": "மோசடி ஏற்படும் அதிக ஆபத்து கண்டறியப்பட்டது. உங்கள் பணத்தைப் பாதுகாக்க இந்தக் கட்டணம் தடுக்கப்பட்டுள்ளது.",
    },
}

RECOMMENDATIONS = {
    "LOW": {
        Language.EN: "Proceed with payment.",
        Language.HI: "भुगतान के साथ आगे बढ़ें।",
        Language.TA: "கட்டணத்துடன் தொடரவும்.",
    },
    "MEDIUM": {
        Language.EN: "Verify the recipient's identity before paying.",
        Language.HI: "भुगतान करने से पहले प्राप्तकर्ता की पहचान सत्यापित करें।",
        Language.TA: "கட்டணம் செலுத்துவதற்கு முன் பெறுபவரின் அடையாளத்தை சரிபார்க்கவும்.",
    },
    "HIGH": {
        Language.EN: "Stop and verify the recipient carefully before proceeding.",
        Language.HI: "आगे बढ़ने से पहले प्राप्तकर्ता को ध्यान से सत्यापित करें।",
        Language.TA: "தொடரும் முன் பெறுபவரை கவனமாக சரிபார்க்கவும்.",
    },
    "CRITICAL": {
        Language.EN: "Do not complete payment. Transaction blocked to prevent loss.",
        Language.HI: "भुगतान पूरा न करें। नुकसान से बचने के लिए लेन-देन रोक दिया गया है।",
        Language.TA: "கட்டணத்தை முடிக்க வேண்டாம். இழப்பைத் தடுக்க பரிவர்த்தனை தடுக்கப்பட்டது.",
    },
}


async def explain_risk(request: ExplainRiskRequest) -> ExplainRiskResponse:
    language_name = LANGUAGE_NAMES.get(request.language, "English")
    level_key = request.risk_level.value if hasattr(request.risk_level, "value") else str(request.risk_level)
    reasons_text = "\n".join([f"- {r.reason}" for r in request.reasons]) if request.reasons else "No specific reasons identified."

    prompt = f"""You are a payment safety assistant for Indian users. Explain the following risk assessment in {language_name}.

Risk Score: {request.risk_score}/100
Risk Level: {level_key}
Risk Signals:
{reasons_text}

Instructions:
- Be concise (2-3 sentences max)
- Be actionable and clear, not alarmist
- Use simple, everyday language
- Do NOT invent or add reasons not listed above
- Include a clear recommendation

Respond in this EXACT format (no markdown, just plain text):
Explanation: [your 2-3 sentence explanation]
Recommendation: [one clear action sentence]"""

    try:
        if settings.GEMINI_API_KEY == "placeholder":
            raise ValueError("No Gemini API key configured")

        model = _get_model()
        response = await model.generate_content_async(prompt)
        text = response.text.strip()

        import re
        explanation = ""
        recommendation = ""

        exp_match = re.search(r"(?i)(?:\*\*|\#\#)?\s*Explanation\s*(?:\*\*|\#\#)?\s*:\s*(.+?)(?=(?:\*\*|\#\#)?\s*Recommendation|\Z)", text, re.DOTALL)
        if exp_match:
            explanation = exp_match.group(1).strip()

        rec_match = re.search(r"(?i)(?:\*\*|\#\#)?\s*Recommendation\s*(?:\*\*|\#\#)?\s*:\s*(.+)", text, re.DOTALL)
        if rec_match:
            recommendation = rec_match.group(1).strip()

        if not explanation and not recommendation:
            for line in text.split("\n"):
                stripped = line.strip()
                if stripped.lower().startswith("explanation:"):
                    explanation = stripped[12:].strip()
                elif stripped.lower().startswith("recommendation:"):
                    recommendation = stripped[15:].strip()

        if explanation:
            if not recommendation:
                recommendation = RECOMMENDATIONS.get(level_key, RECOMMENDATIONS["MEDIUM"]).get(request.language, RECOMMENDATIONS["MEDIUM"][Language.EN])
            return ExplainRiskResponse(explanation=explanation, recommendation=recommendation)
        raise ValueError("Empty Gemini response")

    except Exception as e:
        logger.warning("Gemini explanation failed, using fallback", error=str(e))
        fallback_lang = FALLBACK_TEMPLATES.get(request.language, FALLBACK_TEMPLATES[Language.EN])
        base_explanation = fallback_lang.get(level_key, fallback_lang["MEDIUM"])

        if request.reasons:
            reason_summary = "; ".join([r.reason for r in request.reasons[:2]])
            base_explanation += f" Key signals: {reason_summary}."

        recommendation = RECOMMENDATIONS.get(level_key, RECOMMENDATIONS["MEDIUM"]).get(
            request.language, RECOMMENDATIONS["MEDIUM"][Language.EN]
        )
        return ExplainRiskResponse(explanation=base_explanation, recommendation=recommendation)


async def assistant_query(query: str, user_id: str, context: dict, language: Language = Language.EN) -> str:
    language_name = LANGUAGE_NAMES.get(language, "English")

    # Build a clean, structured context string
    txns = context.get("recent_transactions", [])
    txn_summary = ""
    if txns:
        total_spent = sum(t.get("amount", 0) for t in txns if t.get("status") == "captured")
        high_risk = [t for t in txns if t.get("risk_level") == "HIGH"]
        txn_summary = (
            f"User has {len(txns)} recent transactions. "
            f"Total spent (captured): ₹{total_spent / 100:.2f}. "
            f"High risk transactions: {len(high_risk)}."
        )

    system_prompt = f"""You are a payment safety AI assistant for Indian users. Answer in {language_name}.
You have access to the user's actual transaction data shown below.
CRITICAL RULES:
- Only answer based on the data provided. Never invent transactions, amounts, or risk scores.
- If you cannot answer from the data, clearly say you don't have that information.
- Be concise, helpful, and friendly.

Transaction Summary: {txn_summary if txn_summary else "No recent transaction data available."}"""

    try:
        if settings.GEMINI_API_KEY == "placeholder":
            raise ValueError("No Gemini API key")

        model = _get_model()
        full_prompt = f"{system_prompt}\n\nUser: {query}\nAssistant:"
        response = await model.generate_content_async(full_prompt)
        return response.text.strip()
    except Exception as e:
        logger.warning("AI assistant unavailable", error=str(e))
        return (
            "AI assistant is temporarily unavailable. "
            "Please check your transaction history directly for payment information."
        )


async def summarize_transaction_risk(transaction_data: dict, risk_decision: dict, language: Language = Language.EN) -> str:
    language_name = LANGUAGE_NAMES.get(language, "English")
    level_key = risk_decision.get("level", "MEDIUM")

    prompt = f"""Summarize this transaction risk assessment in {language_name} for a user in 2-3 sentences:
Amount: ₹{transaction_data.get('amount', 0) / 100:.2f}
Merchant: {transaction_data.get('merchant_name', 'Unknown')}
Risk Score: {risk_decision.get('score', 0)}/100
Risk Level: {level_key}
Status: {transaction_data.get('status', 'Unknown')}

Be concise and actionable."""

    try:
        if settings.GEMINI_API_KEY == "placeholder":
            raise ValueError("No Gemini key")

        model = _get_model()
        response = await model.generate_content_async(prompt)
        return response.text.strip()
    except Exception as e:
        logger.warning("Summarize failed", error=str(e))
        fallback_lang = FALLBACK_TEMPLATES.get(language, FALLBACK_TEMPLATES[Language.EN])
        return fallback_lang.get(level_key, fallback_lang["MEDIUM"])