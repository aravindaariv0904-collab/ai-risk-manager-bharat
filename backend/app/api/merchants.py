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

    # 1. Check if search_term is a UPI QR URI
    if search_term.startswith("upi://pay?") or "pa=" in search_term:
        try:
            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(search_term).query)
            pa = parsed.get("pa", [""])[0]  # UPI ID
            pn = parsed.get("pn", [""])[0]  # Merchant Name
            if pa:
                search_term = pa
            elif pn:
                search_term = pn
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
                return MerchantResponse(**res)

    # 3. Search merchants table by business_name (ILIKE)
    m_name = supabase.table("merchants").select("*").ilike("business_name", f"%{search_term}%").limit(1).execute()
    if m_name.data:
        m = dict(m_name.data[0])
        u_res = supabase.table("users").select("phone").eq("id", m.get("user_id")).maybe_single().execute()
        if u_res.data:
            m["phone"] = u_res.data.get("phone")
        return MerchantResponse(**m)

    # 5. Dynamic Auto-Resolution for Real-world PhonePe / GPay / Paytm QRs or UPI IDs
    # If the user scanned or typed a valid UPI ID (e.g. name@okhdfcbank, name@ybl, name@paytm)
    is_upi_string = "@" in search_term or "pa=" in (phone or q or "")
    if is_upi_string:
        upi_name = "UPI Merchant"
        upi_id_val = search_term
        mcc_code = None

        raw = phone or q or ""
        if "pa=" in raw:
            try:
                parsed = urllib.parse.parse_qs(urllib.parse.urlparse(raw).query)
                upi_id_val = parsed.get("pa", [search_term])[0]
                upi_name = parsed.get("pn", [upi_id_val.split("@")[0]])[0]
                mcc_code = parsed.get("mc", [None])[0]
            except Exception:
                pass
        elif "@" in search_term:
            upi_name = search_term.split("@")[0].replace(".", " ").replace("_", " ").title()

        # Map MCC code to category if present
        mcc_map = {
            "5411": "Grocery & Supermarket",
            "5812": "Restaurants & Dining",
            "5814": "Fast Food & Tea",
            "5651": "Clothing & Apparel",
            "5912": "Pharmacy & Healthcare",
            "5311": "Department Store",
        }
        category = mcc_map.get(mcc_code, "Retail & Services")

        # Auto-create or find dynamically in database
        try:
            # Check if exists by upi name
            existing = supabase.table("merchants").select("*").ilike("business_name", f"%{upi_name}%").maybe_single().execute()
            if existing.data:
                return MerchantResponse(**existing.data)

            # Create on-the-fly for real-time risk assessment
            import uuid
            new_merchant = {
                "id": str(uuid.uuid4()),
                "user_id": "d83675e1-4899-4671-81a2-c76e921cb9c8", # Link to system user profile
                "business_name": upi_name,
                "business_category": category,
                "risk_profile": {
                    "baseline_safety": "verified_upi",
                    "source": "live_qr_scan",
                    "vpa": upi_id_val,
                }
            }
            ins_res = supabase.table("merchants").insert(new_merchant).execute()
            if ins_res.data:
                created = ins_res.data if isinstance(ins_res.data, dict) else (ins_res.data[0] if ins_res.data else new_merchant)
                return MerchantResponse(**created)
        except Exception:
            pass

    return None


@router.get("", response_model=List[MerchantResponse])
async def list_merchants(user_id: str = Depends(get_current_user_id)):
    supabase = get_supabase_admin()
    result = supabase.table("merchants").select("*").order("business_name").execute()
    return [MerchantResponse(**m) for m in (result.data or [])]


@router.get("/{merchant_id}", response_model=MerchantResponse)
async def get_merchant(
    merchant_id: str,
    user_id: str = Depends(get_current_user_id),
):
    supabase = get_supabase_admin()
    result = supabase.table("merchants").select("*").eq("id", merchant_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Merchant not found")
    return MerchantResponse(**result.data)