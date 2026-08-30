from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
import re
import urllib.parse

from app.schemas import MerchantResponse
from app.security.auth import get_current_user_id
from app.services.supabase_client import get_supabase_admin

router = APIRouter(prefix="/api/merchants", tags=["merchants"])


@router.get("/lookup", response_model=Optional[MerchantResponse])
async def lookup_merchant(
    q: Optional[str] = Query(None, description="Mobile number, UPI ID, QR payload, or Name"),
    phone: Optional[str] = Query(None),
    user_id: str = Depends(get_current_user_id),
):
    """
    Identify a merchant by:
    1. 10-digit mobile number (e.g. 9812345670, +91 9812345670)
    2. UPI ID (e.g. ramesh@upi, 9812345670@paytm) or QR payload (upi://pay?pa=...&pn=...)
    3. Business Name / Merchant ID
    """
    supabase = get_supabase_admin()
    search_term = (phone or q or "").strip()
    if not search_term:
        return None

    # 1. Process QR URI payload or UPI ID
    raw = (phone or q or "").strip()
    if raw.startswith("upi://pay?") or "pa=" in raw:
        try:
            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(raw).query)
            pa = parsed.get("pa", [""])[0].strip()
            pn_raw = parsed.get("pn", [""])[0]
            pn = urllib.parse.unquote(pn_raw).strip().strip("'\"")
            mc = parsed.get("mc", [None])[0]

            upi_name = pn or (pa.split("@")[0].title() if "@" in pa else "UPI Merchant")

            mcc_map = {
                "5411": "Grocery & Supermarket",
                "5812": "Restaurants & Dining",
                "5814": "Fast Food & Tea",
                "5651": "Clothing & Apparel",
                "5912": "Pharmacy & Healthcare",
                "5311": "Department Store",
            }
            category = mcc_map.get(mc, "Retail & Services")

            # Check if this merchant already exists
            existing = supabase.table("merchants").select("*").ilike("business_name", f"%{upi_name}%").maybe_single().execute()
            if existing.data:
                res = dict(existing.data)
                res["upi_id"] = pa
                res["is_verified"] = res.get("risk_profile", {}).get("is_verified", False)
                return MerchantResponse(**res)

            # Dynamically register new external merchant as UNVERIFIED
            import uuid
            new_id = str(uuid.uuid4())
            new_merchant = {
                "id": new_id,
                "user_id": "d83675e1-4899-4671-81a2-c76e921cb9c8",
                "business_name": upi_name,
                "business_category": category,
                "risk_profile": {
                    "baseline_safety": "unverified_upi",
                    "is_verified": False,
                    "source": "external_qr_scan",
                    "vpa": pa,
                }
            }
            ins_res = supabase.table("merchants").insert(new_merchant).execute()
            created_data = ins_res.data[0] if (ins_res.data and isinstance(ins_res.data, list)) else (ins_res.data or new_merchant)
            created_data["upi_id"] = pa
            created_data["is_verified"] = False
            return MerchantResponse(**created_data)
        except Exception:
            pass

    # 2. Extract digits if it resembles a phone number
    digits = re.sub(r"\D", "", search_term)
    if len(digits) >= 10:
        phone_10 = digits[-10:]
        user_res = supabase.table("users").select("id, name, phone").like("phone", f"%{phone_10}%").execute()
        if user_res.data:
            matched_user = user_res.data[0]
            m_res = supabase.table("merchants").select("*").eq("user_id", matched_user["id"]).maybe_single().execute()
            if m_res.data:
                res = dict(m_res.data)
                res["phone"] = matched_user.get("phone")
                res["is_verified"] = True
                return MerchantResponse(**res)

    # 3. Search merchants table by business_name (ILIKE)
    m_name = supabase.table("merchants").select("*").ilike("business_name", f"%{search_term}%").limit(1).execute()
    if m_name.data:
        m = dict(m_name.data[0])
        u_res = supabase.table("users").select("phone").eq("id", m.get("user_id")).maybe_single().execute()
        if u_res.data:
            m["phone"] = u_res.data.get("phone")
        m["is_verified"] = True
        return MerchantResponse(**m)

    # 4. Handle standalone UPI handle (e.g. name@okhdfcbank)
    if "@" in search_term:
        clean_name = search_term.split("@")[0].replace(".", " ").replace("_", " ").title()
        import uuid
        new_merchant = {
            "id": str(uuid.uuid4()),
            "user_id": "d83675e1-4899-4671-81a2-c76e921cb9c8",
            "business_name": clean_name,
            "business_category": "Retail & Services",
            "risk_profile": {"vpa": search_term, "is_verified": False, "baseline_safety": "unverified_upi"}
        }
        ins_res = supabase.table("merchants").insert(new_merchant).execute()
        created_data = ins_res.data[0] if (ins_res.data and isinstance(ins_res.data, list)) else (ins_res.data or new_merchant)
        created_data["upi_id"] = search_term
        created_data["is_verified"] = False
        return MerchantResponse(**created_data)

    return None


@router.get("", response_model=List[MerchantResponse])
async def list_merchants(user_id: str = Depends(get_current_user_id)):
    supabase = get_supabase_admin()
    result = supabase.table("merchants").select("*").order("business_name").execute()
    merchants = []
    for m in (result.data or []):
        item = dict(m)
        item["is_verified"] = item.get("risk_profile", {}).get("is_verified", True)
        merchants.append(MerchantResponse(**item))
    return merchants


@router.get("/{merchant_id}", response_model=MerchantResponse)
async def get_merchant(
    merchant_id: str,
    user_id: str = Depends(get_current_user_id),
):
    supabase = get_supabase_admin()
    result = supabase.table("merchants").select("*").eq("id", merchant_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Merchant not found")
    res = dict(result.data)
    res["is_verified"] = res.get("risk_profile", {}).get("is_verified", True)
    return MerchantResponse(**res)