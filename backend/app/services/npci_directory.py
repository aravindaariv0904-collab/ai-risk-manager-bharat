"""
Merchant & Counterparty Lookup Service.
Resolves counterparty details from connected banking APIs (when credentials configured)
or from the internal verified merchant database.

FUTURE INTEGRATION: Government / regulated risk data sources, subject to authorized API access.
"""

import os
import re
import httpx
from typing import Dict, Optional

# Verified Local Directory (Seeded merchants & verified accounts)
KNOWN_DIRECTORY = {
    "9963170070": {
        "name": "RAVI KUMAR",
        "bank": "Yes Bank",
        "vpa": "9963170070@ybl",
        "kyc_status": "VERIFIED_FULL_KYC",
    },
    "7396660904": {
        "name": "ARAVIND AARIV",
        "bank": "HDFC Bank",
        "vpa": "7396660904@okhdfcbank",
        "kyc_status": "VERIFIED_FULL_KYC",
    },
    "9812345670": {
        "name": "RAMESH GENERAL STORE",
        "bank": "State Bank of India",
        "vpa": "ramesh@upi",
        "kyc_status": "VERIFIED_MERCHANT",
    },
    "9876543210": {
        "name": "SURESH TEA STALL",
        "bank": "Canara Bank",
        "vpa": "suresh@paytm",
        "kyc_status": "VERIFIED_MERCHANT",
    },
    "9848012345": {
        "name": "LAKSHMI FLOWER SHOP",
        "bank": "ICICI Bank",
        "vpa": "lakshmi@icici",
        "kyc_status": "VERIFIED_MERCHANT",
    },
}


class NPCIDirectoryService:
    @staticmethod
    async def resolve_phone(phone_10: str) -> Optional[Dict]:
        """
        Resolve a 10-digit Indian phone number:
        1. Queries Live Banking API (e.g. Setu / Cashfree) if API Keys are configured.
        2. Checks internal verified merchant database.
        3. Returns None if unknown (avoids fake/random generated names).
        """
        digits = re.sub(r"\D", "", phone_10)[-10:]
        if len(digits) < 10:
            return None

        # 1. Live Banking Provider (Setu API) if configured in backend/.env
        setu_client_id = os.getenv("SETU_CLIENT_ID")
        setu_secret = os.getenv("SETU_CLIENT_SECRET")
        product_instance_id = os.getenv("SETU_PRODUCT_INSTANCE_ID", setu_client_id)

        if setu_client_id and setu_secret:
            headers = {
                "x-client-id": setu_client_id,
                "x-client-secret": setu_secret,
                "x-product-instance-id": product_instance_id,
                "content-type": "application/json",
            }
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    for endpoint in [
                        "https://dg-sandbox.setu.co/api/verify/upi",
                        "https://dg-sandbox.setu.co/api/verify/vpa",
                        "https://prod.setu.co/api/v1/verify/vpa",
                    ]:
                        try:
                            resp = await client.post(endpoint, headers=headers, json={"vpa": f"{digits}@upi"})
                            if resp.status_code == 200:
                                data = resp.json()
                                return {
                                    "name": (data.get("name") or data.get("account_holder_name") or "").upper(),
                                    "bank": data.get("bank_name", "Indian Banking Network"),
                                    "vpa": f"{digits}@upi",
                                    "phone": f"+91 {digits}",
                                    "kyc_status": "VERIFIED_FULL_KYC",
                                    "is_verified": True,
                                    "provider": "Banking API Switch",
                                }
                        except Exception:
                            continue
            except Exception:
                pass

        # 2. Check Known Verified Merchant Registry
        if digits in KNOWN_DIRECTORY:
            record = KNOWN_DIRECTORY[digits]
            return {
                "name": record["name"],
                "bank": record["bank"],
                "vpa": record["vpa"],
                "phone": f"+91 {digits}",
                "kyc_status": record["kyc_status"],
                "is_verified": True,
                "provider": "Verified Merchant Directory",
            }

        # 3. If not in directory and no live bank API key, return None
        return None


npci_directory = NPCIDirectoryService()
